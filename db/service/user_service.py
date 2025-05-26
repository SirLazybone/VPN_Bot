from sqlalchemy import select
from db.models import User
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from config.config import VPN_PRICE
from sheets.sheets import add_user_to_sheets, update_user_by_telegram_id
import asyncio


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
        balance=VPN_PRICE,
        is_active=False
    )
    session.add(new_user)
    await session.commit()
    await asyncio.gather(add_user_to_sheets(new_user))  # добавляем пользователя в google sheets
    return new_user

async def get_user_by_username(session: AsyncSession, username: str) -> User:
    """Находит пользователя по username"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()



async def update_user_balance(session: AsyncSession, username: str, amount: float) -> bool:
    """Обновляет баланс пользователя"""
    user = await get_user_by_username(session, username)
    if not user:
        return False
    
    user.balance += amount
    await session.commit()
    await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
    return True


async def renew_subscription(session: AsyncSession, user_id: int, days: int) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return False
    
    balance = user.balance

    if balance < VPN_PRICE:
        return False
    
    user.balance -= VPN_PRICE

    now = datetime.utcnow()

    # Продлеваем от текущего времени, если подписка отсутствует или уже истекла
    base_time = user.subscription_end if user.subscription_end and user.subscription_end > now else now
    user.subscription_start = user.subscription_start
    user.subscription_end = base_time + timedelta(days=days)
    user.is_active = True

    await session.commit()
    await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
    return True
