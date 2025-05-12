from sqlalchemy import select
from db.models import User
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

async def is_user_exist(session: AsyncSession, username) -> bool:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    return user is not None


async def get_or_create_user(session, user_data):
    result = await session.execute(select(User).where(User.telegram_id == user_data.id))
    user = result.scalar_one_or_none()
    if user:
        return user
    new_user = User(
        telegram_id=user_data.id,
        username=user_data.username,
        balance=149,
        is_active=True
    )
    session.add(new_user)
    await session.commit()
    return new_user

async def get_user_by_username(session: AsyncSession, username: str) -> User:
    """Находит пользователя по username"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def renew_subscription(session: AsyncSession, user_id: int, days: int) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False
    
    balance = user.balance

    if balance < 149:
        return False
    
    user.balance -= 149

    now = datetime.utcnow()

    # Продлеваем от текущего времени, если подписка отсутствует или уже истекла
    base_time = user.subscription_end if user.subscription_end and user.subscription_end > now else now
    user.subscription_start = user.subscription_start
    user.subscription_end = base_time + timedelta(days=days)
    user.is_active = True

    await session.commit()
    return True
