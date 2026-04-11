from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lib.database.utils import get_db
from lib.ai.google_api.gemini_client import generate_answer_with_memory
from lib.ncc.api.v1.schemas.chat_schemas import ChatRequest, ChatResponse
from lib.ncc.services.chat_services import get_or_create_session, save_message, get_formatted_history, get_rag_context


v1_chat_bp = APIRouter()


@v1_chat_bp.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_with_memory_and_rag(payload: ChatRequest, db: Session = Depends(get_db)):
    """企业级聊天接口：融合 RAG 检索与多轮滑动窗口记忆"""
    try:
        # 1. Session & User Input
        session_id = get_or_create_session(db, payload.session_id, payload.message)
        save_message(db, session_id, "user", payload.message)

        # 2. Load Memory & Knowledge
        history = get_formatted_history(db, session_id, limit=10)
        context, sources = get_rag_context(db, payload.message)

        # 3. AI Generation
        ai_answer = generate_answer_with_memory(
            question=payload.message,
            context=context,
            history=history[:-1]  # 排除当前提问，防止 Gemini 报错重复
        )

        # 4. Save AI Response & Commit
        save_message(db, session_id, "model", ai_answer)
        db.commit()

        return ChatResponse(
            session_id=session_id,
            answer=ai_answer,
            sources=sources
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
