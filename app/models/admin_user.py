"""Admin user model for authentication and RBAC."""

import enum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(enum.StrEnum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class AdminUser(UUIDMixin, TimestampMixin, Base):
    """Internal staff user for the fraud-ops portal."""

    __tablename__ = "admin_users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.viewer.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
