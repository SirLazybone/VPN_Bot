from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from db.models import User, Payment

async def create_payment(
    session: AsyncSession,
    user_id: int,
    nickname: str,
    message: str = None,
    pay_system: str = None,
) -> Payment:
    """Создает новую запись о платеже"""
    payment = Payment(
        user_id=user_id,
        status='pending',
        nickname=nickname,
        message=message,
        pay_system=pay_system
    )
    session.add(payment)
    await session.commit()
    return payment


async def get_user_payments(session: AsyncSession, user_id: int) -> list[Payment]:
    """Получает все платежи пользователя"""
    stmt = select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()

async def get_payment_by_id(session: AsyncSession, id: int) -> Payment:
    stmt = select(Payment).where(Payment.id == id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def check_subscription_status(session: AsyncSession, user_id: int) -> bool:
    """Проверяет статус подписки пользователя"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.subscription_start:
        return False
        
    # Проверяем, не истекла ли подписка (30 дней)
    subscription_end = user.subscription_start + timedelta(days=30)
    return datetime.utcnow() < subscription_end 