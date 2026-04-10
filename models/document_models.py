from typing import List

from models.base import Base, BlameMixin

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Text, Integer, ForeignKey, VARCHAR
from pgvector.sqlalchemy import Vector


class Document(Base, BlameMixin):
    """
    Main document table storing metadata such as title and source.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    source: Mapped[str] = mapped_column(VARCHAR(500), nullable=True)

    # One-to-Many relationship: One document has many chunks
    # cascade="all, delete-orphan" ensures chunks are cleaned up when a document is deleted
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title})>"


class DocumentChunk(Base, BlameMixin):
    """
    Stores actual text content and its corresponding vector embedding.
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign key link to the parent document
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )

    # Text content and its metadata
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=True)

    # Order of the chunk within the original document
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 768-dimensional vector for semantic search
    embedding: Mapped[Vector] = mapped_column(Vector(768), nullable=True)

    # Relationship back to the parent document
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"
