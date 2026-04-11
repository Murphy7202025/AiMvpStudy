from models.base import Base, BlameMixin, DeletableMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Text, VARCHAR, Boolean, Integer, ForeignKey
from typing import List


class ChatSession(Base, BlameMixin):
    """
    Chat Session Model: represents a single conversation thread.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(VARCHAR(255), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # One-to-Many relationship with messages
    # cascade="all, delete-orphan" Ensures physical deletion cleans up child rows if needed
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title={self.title})>"


class ChatMessage(Base, BlameMixin, DeletableMixin):
    """
    Chat Message Model: represents individual interactions within a session.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign Key pointing to the parent session
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    # user, model, or system
    role: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)

    # The actual text content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # For cost and context window tracking
    token_count: Mapped[int] = mapped_column(Integer, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Back reference to the parent session
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role={self.role})>"
