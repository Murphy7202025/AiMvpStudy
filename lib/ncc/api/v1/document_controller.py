from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import selectinload, Session

from lib.database.utils import get_db
from lib.ai.google_api.gemini_client import get_text_embedding, generate_answer_from_context
from lib.ncc.api.v1.schemas.document_schemas import DocumentCreate, DocumentDetailResponse, DocumentSearchResult, \
    DocumentSearchRequest, AskResponse, AskRequest, DocumentChunkItem
from models.document_models import Document, DocumentChunk

from fastapi import APIRouter, HTTPException, Depends
from typing import List


DOCUMENTS = "documents"
SEARCH = "search"
ASK = "ask"

v1_document_bp = APIRouter()


@v1_document_bp.get(f"/{DOCUMENTS}", tags=[DOCUMENTS])
async def get_documents(session: Session = Depends(get_db)) -> List[DocumentDetailResponse]:
    """获取所有文档列表（带50字符内容预览）"""
    try:
        # 1. 使用 selectinload 一次性查出 Document 和关联的 chunks，防止 N+1 查询导致卡顿
        docs = session.query(Document).options(selectinload(Document.chunks)).all()

        result_list = []
        for doc in docs:
            preview = ""
            # 2. 如果该文档有内容切片，找到第一片 (chunk_index=0)
            if doc.chunks:
                # 确保按照 chunk_index 排序，拿到真正的文章开头
                first_chunk = next((c for c in doc.chunks if c.chunk_index == 0), doc.chunks[0])
                # 3. 截取前 50 个字符，超出的部分加上省略号
                preview = first_chunk.content[:50] + "..." if len(first_chunk.content) > 50 else first_chunk.content
            # 4. 手动组装响应对象
            result_list.append(DocumentDetailResponse(
                id=doc.id,
                title=doc.title,
                source=doc.source,
                content=preview
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
        results = (
            session.query(
                DocumentChunk.id,
                DocumentChunk.content,
                DocumentChunk.document_id,
                Document.title.label("document_title"),  # Join parent title
                # 计算当前文档与用户问题的余弦距离，并将其命名为 distance
                DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            # 按距离从小到大排序（距离越小，语义越接近）
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            # 限制返回条数
            .limit(payload.top_k)
            .all()
        )

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
