from models.base import Base

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, Text
from pgvector.sqlalchemy import Vector


class Document(Base):
    __tablename__ = "documents"

    # 主键 ID
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 存储原始文本内容
    content: Mapped[str] = mapped_column(Text)

    # 存储向量坐标 (Gemini 2.5/3 的 Embedding 维度通常是 768)
    embedding: Mapped[Vector] = mapped_column(Vector(768))

    def __repr__(self) -> str:
        return f"Document(id={self.id!r}, content={self.content[:20]!r}...)"
