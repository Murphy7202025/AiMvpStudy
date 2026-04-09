from lib.ncc.api.v1.schemas import BaseSchema

from pydantic import Field, field_validator
from typing import List, Optional, Any


class DocumentCreate(BaseSchema):
    """用于接收前端传来的 JSON 数据"""
    content: str = Field(..., description="文档的具体内容", min_length=1)


class DocumentItem(BaseSchema):
    """列表接口返回的单个文档格式"""
    id: int = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")


class DocumentDetailResponse(BaseSchema):
    """新增成功后返回的详细信息格式"""
    id: int
    content: str
    embedding: Optional[List[float]] = Field(
        None,
        description="向量的前20个维度预览",
        max_length=20,
        alias="embedding_preview"
    )

    @field_validator("embedding", mode="before")
    def slice_embedding(cls, v: Any):
        if v is not None:
            try:
                # pgvector 返回的是 ndarray，强转为 list 并切取前 20 个！
                # 这样 Pydantic 后续拿到做校验的，就已经是 20 维的标准列表了
                return list(v)[:20]

            except Exception:
                return None

        else:
            return None


# --- 搜索请求体 ---
class DocumentSearchRequest(BaseSchema):
    """用于接收前端传来的搜索提问"""
    query: str = Field(..., description="用户的搜索问题", min_length=1)

    # ge=1 表示大于等于1，le=20 表示小于等于20。防止恶意请求拉爆数据库
    top_k: int = Field(default=5, description="返回最相似的前几条结果", ge=1, le=20)


# --- 搜索响应体 ---
class DocumentSearchResult(BaseSchema):
    """搜索接口返回的单条结果格式"""
    id: int
    content: str
    distance: float = Field(..., description="向量余弦距离（值越小，代表语义越接近）")
