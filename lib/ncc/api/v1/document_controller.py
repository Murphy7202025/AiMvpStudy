from fastapi import APIRouter
from lib.database.utils import session
from models.document_models import Document

v1_document_bp = APIRouter()


@v1_document_bp.get("/documents", tags=["Documents"])
async def get_documents():
    docs = session.query(Document).all()
    return docs


@v1_document_bp.post("/documents", tags=["Documents"])
async def add_document(content: str):
    new_doc = Document(content=content)
    session.add(new_doc)
    session.commit()
    session.refresh(new_doc)
    return new_doc
