from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from db.models import User, Payment
import asyncio

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

async def get_payment_by_payment_id(session: AsyncSession, payment_id) -> Payment:
    stmt = select(Payment).where(Payment.payment_id == payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_payment_id(session: AsyncSession, id, payment_id) -> Payment:
    stmt = select(Payment).where(Payment.id == id)
    result = await session.execute(stmt)
    payment = result.scalar_one_or_none()
    if not payment:
        return None
    payment.payment_id = payment_id
    await session.commit()
    return payment

async def update_payment_status(
    session: AsyncSession,
    id: int,
    status: str,
    amount: float = None,
    payment_id: str = None,
    completed_at: datetime = None,
    pay_system: str = None
) -> Payment:
    """Обновляет статус платежа и связанные данные"""
    stmt = select(Payment).where(Payment.id == id)
    result = await session.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        return None
    
    payment.status = status
    if amount is not None:
        payment.amount = amount
    if payment_id:
        payment.payment_id = payment_id
    if completed_at:
        payment.completed_at = completed_at
    if pay_system:
        payment.pay_system = pay_system

    await session.commit()
    return payment
