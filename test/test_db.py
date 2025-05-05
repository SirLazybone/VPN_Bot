import asyncio
from datetime import datetime
from db.database import async_session
from db.models import User, Payment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.service.user_service import get_or_create_user
from aiogram.types import User as TelegramUser

async def test_database_operations():
    try:
        # Создаем тестового пользователя
        async with async_session() as session:
            # Создаем нового пользователя
            new_user = User(
                telegram_id=123456789,
                username="test_user",
                balance=100.0,
                is_active=True
            )
            session.add(new_user)
            await session.commit()
            print("✅ Пользователь успешно создан")
            
            # Создаем тестовый платеж
            new_payment = Payment(
                user_id=new_user.id,
                amount=150.0,
                payment_id="test_payment_123",
                status="completed",
                completed_at=datetime.utcnow()
            )
            session.add(new_payment)
            await session.commit()
            print("✅ Платеж успешно создан")
            
            # Получаем пользователя и его платежи
            user = await session.get(User, new_user.id)
            print(f"✅ Получен пользователь: {user.username} (ID: {user.id})")
            
            # Получаем платежи пользователя
            payments = await session.execute(
                select(Payment).where(Payment.user_id == user.id)
            )
            payments = payments.scalars().all()
            print(f"✅ Найдено платежей: {len(payments)}")
            for payment in payments:
                print(f"  - Платеж {payment.id}: {payment.amount} руб., статус: {payment.status}")
            
            # Обновляем баланс пользователя
            user.balance += 50.0
            await session.commit()
            print(f"✅ Баланс пользователя обновлен: {user.balance} руб.")
            
    except Exception as e:
        print(f"❌ Ошибка при работе с базой данных: {e}")

async def test_balance_update():
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == 1471983284))
        user = result.scalar_one_or_none()
        # Получаем или создаем пользователя
        print(f"Текущий баланс пользователя: {user.balance}")
        
        # Увеличиваем баланс на n
        n = 300  # Можно изменить на нужное значение
        user.balance += n
        print(f"Новый баланс после добавления {n}: {user.balance}")
        
        # Сохраняем изменения
        await session.commit()
        
        # Обновляем объект из базы данных
        await session.refresh(user)
        print(f"Баланс после сохранения: {user.balance}")

if __name__ == "__main__":
    # asyncio.run(test_database_operations())
    asyncio.run(test_balance_update()) 