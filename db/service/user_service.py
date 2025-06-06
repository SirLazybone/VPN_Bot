from sqlalchemy import select
from db.models import User
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from config.config import VPN_PRICE
import asyncio


async def is_user_exist(session: AsyncSession, telegram_id) -> bool:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    return user is not None


async def get_or_create_user(session, user_data):
    result = await session.execute(select(User).where(User.telegram_id == user_data.id))
    user = result.scalar_one_or_none()
    if user:
        return user
    if user_data.username is None or user_data.username == '' or len(user_data.username) < 4:
        new_user = User(
            telegram_id=user_data.id,
            username=user_data.id,
            balance=VPN_PRICE,
            is_active=False
        )
    else:
        new_user = User(
            telegram_id=user_data.id,
            username=user_data.username,
            balance=VPN_PRICE,
            is_active=False
        )

    session.add(new_user)
    await session.commit()
    return new_user

async def get_user_by_username(session: AsyncSession, username: str) -> User:
    """Находит пользователя по username"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def get_user_by_telegram_id(session: AsyncSession, telegram_id) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def update_user_balance(session: AsyncSession, username: str, amount: float) -> bool:
    """Обновляет баланс пользователя"""
    user = await get_user_by_username(session, username)
    if not user:
        return False
    
    user.balance += amount
    await session.commit()
    return True


async def renew_subscription(session: AsyncSession, user_id: int, days: int, price: int = VPN_PRICE) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False

    if price != 0:
        balance = user.balance
        if balance < price:
            return False
        user.balance -= price

    now = datetime.utcnow()

    # Продлеваем от текущего времени, если подписка отсутствует или уже истекла
    base_time = user.subscription_end if user.subscription_end and user.subscription_end > now else now
    user.subscription_start = user.subscription_start
    user.subscription_end = base_time + timedelta(days=days)
    user.is_active = True

    await session.commit()
    return True


async def get_all_users(session: AsyncSession):
    result = await session.execute(select(User))
    users = result.scalars().all()

    return users
