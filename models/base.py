from sqlalchemy.orm import DeclarativeBase
import sqlalchemy as sa
import datetime


class Base(DeclarativeBase):
    pass


class BlameMixin:
    """
    Mixin to add audit columns: created_at, updated_at, created_by, and updated_by.
    """
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Audit fields default to None until user management is implemented
    created_by = sa.Column(sa.Unicode(100), nullable=True, default=None)
    updated_by = sa.Column(sa.Unicode(100), nullable=True, default=None, onupdate=None)

    def reset_blame_for_versioning(self):
        """
        Resets audit attributes to None for versioning purposes.
        """
        self.created_by = None
        self.created_at = None
        self.updated_by = None
        self.updated_at = None


class DeletableMixin:
    """
    Adds soft delete columns to models.
    """
    deleted_at = sa.Column(sa.DateTime, nullable=True)
    deleted_by = sa.Column(sa.Unicode(100), nullable=True)
