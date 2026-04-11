from lib.database.utils import get_db
from lib.ai.google_api.gemini_client import get_text_embedding, generate_answer_from_context, \
    generate_answer_with_search
from lib.ncc.api.v1.schemas.document_schemas import DocumentCreate, DocumentDetailResponse, DocumentSearchResult, \
    DocumentSearchRequest, AskResponse, AskRequest, DocumentChunkItem
from lib.ncc.services.document_services import process_and_store_document, get_document_preview, \
    get_similar_chunks_with_distance, get_top_chunk_with_score, search_documents_by_vector
from models.document_models import Document, DocumentChunk

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import selectinload, Session
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import List, Optional


DOCUMENTS = "documents"
SEARCH = "search"
ASK = "ask"
UPLOAD = "upload"
RESEARCH = "research"

v1_document_bp = APIRouter()


@v1_document_bp.get(f"/{DOCUMENTS}", tags=[DOCUMENTS])
async def get_documents(session: Session = Depends(get_db)) -> List[DocumentDetailResponse]:
    """获取所有文档列表（带50字符内容预览）"""
    try:
        # 1. 使用 selectinload 一次性查出 Document 和关联的 chunks，防止 N+1 查询导致卡顿
        docs = session.query(Document).options(selectinload(Document.chunks)).all()

        result_list = []
        for doc in docs:
            # 2. 手动组装响应对象
            result_list.append(DocumentDetailResponse(
                id=doc.id,
                title=doc.title,
                source=doc.source,
                content=get_document_preview(doc)
            ))

        return result_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@v1_document_bp.post(f"/{DOCUMENTS}", tags=[DOCUMENTS])
async def add_document(payload: DocumentCreate, db: Session = Depends(get_db)) -> DocumentDetailResponse:
    """新增文档并使用生产级切片算法生成向量"""
    try:
        # 1. 实例化生产级文本切分器
        # 这里针对中文环境做了优化，分隔符优先考虑中文标点
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            chunk_size=800,       # 经验值：每个分块最大 800 字符，适合大部分 LLM
            chunk_overlap=150,    # 经验值：保留 150 字符的重叠，防止上下文断裂
            length_function=len,
            is_separator_regex=False,
        )

        # 2. 执行智能切片
        print(f"--- ✂️ 正在执行智能切片... ---")
        raw_chunks = text_splitter.split_text(payload.content)
        print(f"--- ✅ 切片完成，共分为 {len(raw_chunks)} 块 ---")

        # 3. 开启数据库事务
        # 保存父级文档元数据
        new_doc = Document(
            title=payload.title,
            source=payload.source
        )
        db.add(new_doc)
        db.flush()  # 获取新插入文档的 ID

        # 4. 遍历切片，生成向量并入库
        for i, text_segment in enumerate(raw_chunks):
            # print(f"--- ⏳ 正在为第 {i+1} 块生成向量... ---")
            vector = get_text_embedding(text_segment)

            chunk = DocumentChunk(
                document_id=new_doc.id,
                content=text_segment,
                content_length=len(text_segment),
                chunk_index=i,
                embedding=vector
            )
            db.add(chunk)

        # 5. 提交事务
        db.commit()
        db.refresh(new_doc)

        # 1. 构造预览文本（取 payload 原始文本的前 50 字）
        preview = payload.content[:50] + "..." if len(payload.content) > 50 else payload.content

        # 2. 先生成响应对象
        response_data = DocumentDetailResponse.model_validate(new_doc)

        # 3. 手动注入预览内容，补齐模型中缺失的字段
        response_data.content = preview

        return response_data

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{SEARCH}", tags=[DOCUMENTS])
async def search_documents(payload: DocumentSearchRequest, session: Session = Depends(get_db)) -> List[DocumentSearchResult]:
    """基于向量相似度的语义搜索"""
    try:
        print(f"--- 🔍 正在将用户问题转化为向量... ---")
        # 1. 将用户的提问转为向量 (注意: is_query=True)
        query_vector = get_text_embedding(payload.query, is_query=True)

        # 2. 数据库魔法时刻：使用 pgvector 的余弦距离进行排序
        # .cosine_distance() 是 pgvector 扩展专门为 SQLAlchemy 提供的方法
        results = search_documents_by_vector(session, query_vector, payload.top_k)

        return [DocumentSearchResult.model_validate(result) for result in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{ASK}", tags=[DOCUMENTS])
async def ask_knowledge_base(payload: AskRequest, session: Session = Depends(get_db)) -> AskResponse:
    """基于知识库的 AI 智能问答 (RAG 核心链路)"""
    try:
        print(f"--- 🧠 开始处理用户提问: {payload.question} ---")

        # 1. 把用户的问题变成向量
        query_vector = get_text_embedding(payload.question, is_query=True)

        # 2. 从数据库搜出最相关的 3 条资料 (距离越小越好，限制距离在 0.6 以内保证相关性)
        results = (
            session.query(DocumentChunk)  # Changed from Document
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(3)
            .all()
        )

        if not results:
            return AskResponse(answer="抱歉，知识库中暂时没有相关资料。", sources=[])

        # 3. 把搜出来的资料内容拼接成一大段文本
        # 给每条资料加上序号，方便大模型阅读
        context_text = "\n".join([f"资料 {i + 1}: {doc.content}" for i, doc in enumerate(results)])
        print(f"--- 📚 检索到相关上下文，长度: {len(context_text)} 字符 ---")

        # 4. 召唤大模型！生成最终回答
        ai_answer = generate_answer_from_context(
            question=payload.question,
            context=context_text
        )

        # 5. 组装并返回（带着答案和参考来源）
        # 使用我们之前写好的 Pydantic model_validate 来转换 ORM 对象
        sources_list = [DocumentChunkItem.model_validate(doc) for doc in results]

        return AskResponse(
            answer=ai_answer,
            sources=sources_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{RESEARCH}", tags=[DOCUMENTS])
async def ask_knowledge_base(payload: AskRequest, session: Session = Depends(get_db)) -> AskResponse:
    """智能体接口：优先本地知识库，不匹配则自动联网搜索"""
    try:
        query_vector = get_text_embedding(payload.question, is_query=True)
        # 1. 快速获取最相关的本地资料
        top_match = get_top_chunk_with_score(session, query_vector)

        # 2. 决策路由：如果距离 > 0.6 或 根本没数据，直接走联网模式
        if not top_match or top_match.distance > 0.6:
            print(f"--- 🌐 Agent 决策：本地知识距离 {top_match.distance if top_match else 'N/A'} 过远，联网搜索 ---")
            answer = generate_answer_with_search(payload.question, context="")
            return AskResponse(answer=answer, sources=[])

        # 3. 命中本地逻辑：获取前 3 条并生成回答
        print(f"--- 📚 Agent 决策：本地命中 (Distance: {top_match.distance}) ---")
        results = get_similar_chunks_with_distance(session, query_vector, limit=3)
        chunks = [row[0] for row in results]
        context = "\n".join([f"资料: {c.content}" for c in chunks])

        # 既然是 Agent，本地回答也可以用 search 函数来增强表现力
        answer = generate_answer_with_search(payload.question, context=context)
        sources = [DocumentChunkItem.model_validate(c) for c in chunks]

        return AskResponse(answer=answer, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{UPLOAD}", tags=[DOCUMENTS])
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None, description="可选文档标题，不传则从文件名提取"),
    session: Session = Depends(get_db)
) -> DocumentDetailResponse:
    """文档上传解析与自动切片向量化 (支持 PDF/TXT)"""
    try:
        # 1. 传入 file 和 title，交给 Service 层处理
        new_doc = await process_and_store_document(session, file, custom_title=title)

        # 2. 构造响应对象
        response_data = DocumentDetailResponse.model_validate(new_doc)

        # 3. 提取第一块作为内容预览
        response_data.content = get_document_preview(new_doc)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
