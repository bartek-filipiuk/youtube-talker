"""
Database Models

SQLAlchemy ORM models for all database tables.
Uses SQLAlchemy 2.0 declarative mapping style.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all database models.

    All models inherit from this class to be tracked by SQLAlchemy
    and included in Alembic migrations.
    """

    pass
