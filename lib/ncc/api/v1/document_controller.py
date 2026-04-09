from google.genai import types

from lib.database.utils import session_scope
from lib.ai.google_api.gemini_client import get_text_embedding, client
from lib.database.utils import session
from lib.ncc.api.v1.schemas.document_schemas import DocumentCreate, DocumentItem, DocumentDetailResponse
from models.document_models import Document

from fastapi import APIRouter, HTTPException
from typing import List


v1_document_bp = APIRouter()


@v1_document_bp.get("/documents", tags=["Documents"])
async def get_documents() -> List[DocumentDetailResponse]:
    """获取所有文档列表"""
    try:
        with session_scope() as db_session:
            # SQLAlchemy 查询出来的是模型对象列表
            docs = db_session.query(Document).all()

            return [DocumentDetailResponse.model_validate(doc) for doc in docs]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@v1_document_bp.post("/documents", tags=["Documents"])
async def add_document(payload: DocumentCreate) -> DocumentDetailResponse:
    """新增文档并自动生成向量"""
    try:
        print(f"--- ⏳ 正在为文本生成向量... ---")
        # 从 payload 中取出 content
        response = client.models.embed_content(
            # 1. 核心修改：使用最新的替代模型
            model="gemini-embedding-001",
            contents=payload.content,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                # 2. 核心防御：强制截断回 768 维，防止数据库的 Vector 长度溢出报错
                output_dimensionality=768
            )
        )

        vector = response.embeddings[0].values
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
