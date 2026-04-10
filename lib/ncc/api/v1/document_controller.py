from lib.database.utils import session_scope
from lib.ai.google_api.gemini_client import get_text_embedding, client, generate_answer_from_context
from lib.database.utils import session
from lib.ncc.api.v1.schemas.document_schemas import DocumentCreate, DocumentDetailResponse, DocumentSearchResult, \
    DocumentSearchRequest, AskResponse, AskRequest, DocumentItem
from models.document_models import Document

from fastapi import APIRouter, HTTPException
from typing import List


DOCUMENTS = "documents"
SEARCH = "search"
ASK = "ask"

v1_document_bp = APIRouter()


@v1_document_bp.get(f"/{DOCUMENTS}", tags=[DOCUMENTS])
async def get_documents() -> List[DocumentDetailResponse]:
    """获取所有文档列表"""
    try:
        with session_scope() as db_session:
            # SQLAlchemy 查询出来的是模型对象列表
            docs = db_session.query(Document).all()

            return [DocumentDetailResponse.model_validate(doc) for doc in docs]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@v1_document_bp.post(f"/{DOCUMENTS}", tags=[DOCUMENTS])
async def add_document(payload: DocumentCreate) -> DocumentDetailResponse:
    """新增文档并自动生成向量"""
    try:
        print(f"--- ⏳ 正在为文本生成向量... ---")
        vector = get_text_embedding(payload.content)
        print(f"--- ✅ 向量生成成功，维度: {len(vector)} ---")

        with session_scope() as db_session:
            new_doc = Document(
                content=payload.content,
                embedding=vector
            )
            db_session.add(new_doc)
            db_session.flush()
            db_session.refresh(new_doc)

            # 返回字典，FastAPI 会根据 DocumentDetailResponse 自动校验和打包
            return DocumentDetailResponse.model_validate(new_doc)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{SEARCH}", tags=[DOCUMENTS])
async def search_documents(payload: DocumentSearchRequest) -> List[DocumentSearchResult]:
    """基于向量相似度的语义搜索"""
    try:
        print(f"--- 🔍 正在将用户问题转化为向量... ---")
        # 1. 将用户的提问转为向量 (注意: is_query=True)
        query_vector = get_text_embedding(payload.query, is_query=True)

        with session_scope() as db_session:
            # 2. 数据库魔法时刻：使用 pgvector 的余弦距离进行排序
            # .cosine_distance() 是 pgvector 扩展专门为 SQLAlchemy 提供的方法
            results = (
                db_session.query(
                    Document.id,
                    Document.content,
                    # 计算当前文档与用户问题的余弦距离，并将其命名为 distance
                    Document.embedding.cosine_distance(query_vector).label("distance")
                )
                # 按距离从小到大排序（距离越小，语义越接近）
                .order_by(Document.embedding.cosine_distance(query_vector))
                # 限制返回条数
                .limit(payload.top_k)
                .all()
            )

            return [DocumentSearchResult.model_validate(result) for result in results]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@v1_document_bp.post(f"/{DOCUMENTS}/{ASK}", tags=[DOCUMENTS])
async def ask_knowledge_base(payload: AskRequest) -> AskResponse:
    """基于知识库的 AI 智能问答 (RAG 核心链路)"""
    try:
        print(f"--- 🧠 开始处理用户提问: {payload.question} ---")

        # 1. 把用户的问题变成向量
        query_vector = get_text_embedding(payload.question, is_query=True)

        with session_scope() as db_session:
            # 2. 从数据库搜出最相关的 3 条资料 (距离越小越好，限制距离在 0.6 以内保证相关性)
            results = (
                db_session.query(Document)
                .order_by(Document.embedding.cosine_distance(query_vector))
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
            sources_list = [DocumentItem.model_validate(doc) for doc in results]

            return AskResponse(
                answer=ai_answer,
                sources=sources_list
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
