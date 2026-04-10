import os
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from lib.ai.google_api.gemini_client import client


# 模仿 Flask Blueprint 命名
v1_chat_bp = APIRouter()

# 存储对话会话 (Session)
# ⚠️ 注意：这是内存存储，服务重启后会话会丢失，后续需要迁移到 Redis
chat_sessions = {}


@v1_chat_bp.get("/chat", tags=["AI Chat"])
async def chat(prompt: str, session_id: str = "default"):
    """
    使用最新版 google-genai SDK 的异步流式接口
    访问路径：/api/v1/chat
    """
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    if session_id not in chat_sessions:
        # 新 SDK 的异步写法：client.aio.chats.create
        chat_sessions[session_id] = client.aio.chats.create(model=model_name)

    chat_obj = chat_sessions[session_id]

    async def event_generator():
        try:
            response_stream = await chat_obj.send_message_stream(prompt)

            async for chunk in response_stream:
                if chunk.text:
                    # 按照 SSE 格式返回
                    yield f"data: {chunk.text}\n\n"
                    # 给前端留一点渲染时间，模拟打字机
                    await asyncio.sleep(0.01)

        except Exception as e:
            yield f"data: [Error]: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
