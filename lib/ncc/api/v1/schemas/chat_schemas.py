from lib.ncc.api.v1.schemas import BaseSchema
from pydantic import Field
from typing import Optional, List
from lib.ncc.api.v1.schemas.document_schemas import DocumentChunkItem


class ChatRequest(BaseSchema):
    """前端发起的聊天请求"""
    # 核心：如果是新对话，前端不传或传 None；如果是老对话，传对应的 ID
    session_id: Optional[int] = Field(default=None, description="会话ID，为空则创建新会话")
    message: str = Field(..., description="用户当前发送的消息", min_length=1)


class ChatResponse(BaseSchema):
    """后端的聊天响应"""
    session_id: int = Field(..., description="当前的会话ID，前端需保存以便发下一句")
    answer: str = Field(..., description="AI 的回答")
