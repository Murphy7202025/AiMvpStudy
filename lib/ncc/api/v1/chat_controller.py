from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from lib.database.utils import get_db
from lib.ai.google_api.gemini_client import generate_answer_with_memory_stream
from lib.ncc.api.v1.schemas.chat_schemas import ChatRequest
from lib.ncc.services.chat_services import get_or_create_session, save_message, get_formatted_history

import json
import asyncio


v1_chat_bp = APIRouter()


@v1_chat_bp.post("/chat", tags=["Chat"])
async def chat_with_memory_and_rag(
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    """流式聊天接口：SSE 格式逐字输出"""
    try:
        session_id = get_or_create_session(db, payload.session_id, payload.message)
        save_message(db, session_id, "user", payload.message)
        history = get_formatted_history(db, session_id, limit=10)
        db.commit()

        full_answer = []

        async def event_generator():
            # 先把 session_id 发给前端
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

            async for chunk in generate_answer_with_memory_stream(
                question=payload.message,
                history=history[:-1]
            ):
                full_answer.append(chunk)
                yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
                await asyncio.sleep(0.1)

            # 流结束后保存完整回答
            save_message(db, session_id, "model", "".join(full_answer))
            db.commit()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
