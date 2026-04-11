from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException
from typing import Tuple, List, Optional

from models.chat_models import ChatSession, ChatMessage
from models.document_models import DocumentChunk
from lib.ncc.api.v1.schemas.document_schemas import DocumentChunkItem
from lib.ai.google_api.gemini_client import get_text_embedding


def get_or_create_session(db: Session, session_id: Optional[int], message: str) -> int:
    """Manage session lifecycle."""
    if not session_id:
        title = message[:20] + "..." if len(message) > 20 else message
        session = ChatSession(title=title)
        db.add(session)
        db.flush()
        return session.id

    if not db.query(ChatSession).filter_by(id=session_id, is_deleted=False).first():
        raise HTTPException(status_code=404, detail="Session not found")
    return session_id


def save_message(db: Session, session_id: int, role: str, content: str) -> None:
    """Save a single chat message."""
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.flush()


def get_formatted_history(db: Session, session_id: int, limit: int = 10) -> List[dict]:
    """Retrieve and format recent chat history for the LLM."""
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id, ChatMessage.is_deleted.is_(False))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    history.reverse()  # LLM needs chronological order

    return [
        {"role": msg.role, "parts": [msg.content]}
        for msg in history if msg.role in ["user", "model"]
    ]


def get_rag_context(db: Session, query: str, top_k: int = 3) -> Tuple[str, List[DocumentChunkItem]]:
    """Retrieve RAG context using vector search."""
    query_vector = get_text_embedding(query, is_query=True)
    chunks = (
        db.query(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )

    if not chunks:
        return "", []

    context_text = "\n".join([f"Source {i + 1}: {c.content}" for i, c in enumerate(chunks)])
    sources_list = [DocumentChunkItem.model_validate(c) for c in chunks]
    return context_text, sources_list
