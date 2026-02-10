"""Repository for admin user data access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_user import AdminUser


class UserRepository:
    """Data access layer for admin users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> AdminUser | None:
        result = await self.session.execute(select(AdminUser).where(AdminUser.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> AdminUser | None:
        result = await self.session.execute(select(AdminUser).where(AdminUser.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: AdminUser) -> AdminUser:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
