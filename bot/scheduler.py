from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.database import async_session
from db.models import User
from sqlalchemy import select, update
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram import types
from config.config import BOT_TOKEN
from sheets.sheets import update_user_by_telegram_id
import asyncio

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

async def get_remaining_subscription_days(telegram_id: int) -> int:
    """
    Возвращает количество оставшихся дней подписки для пользователя
    :param telegram_id: Telegram ID пользователя
    :return: Количество оставшихся дней подписки. Если подписка истекла, возвращает 0
    """
    async with async_session() as session:
        # Находим пользователя
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.subscription_start:
            return 0
            
        # Вычисляем дату окончания подписки
        subscription_end = user.subscription_start + timedelta(days=30)
        remaining_days = (subscription_end - datetime.utcnow()).days
        
        return max(0, remaining_days)  # Возвращаем 0, если подписка истекла

async def check_expired_subscriptions():
    """Проверяет истекшие подписки"""
    async with async_session() as session:
        # Находим пользователей с истекшей подпиской
        expired_date = datetime.utcnow() - timedelta(days=30)
        stmt = select(User).where(
            User.subscription_start < expired_date,
            User.is_active == True
        )
        result = await session.execute(stmt)
        expired_users = result.scalars().all()
        
        # Отправляем уведомления и деактивируем подписки
        for user in expired_users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "⚠️ Ваша подписка истекла!\n\n",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
                                                            [
                                                                [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
                                                            ])
                )
            except Exception as e:
                print(f"Error sending message to user {user.telegram_id}: {e}")
            
            # Деактивируем подписку
            stmt = update(User).where(User.id == user.id).values(is_active=False)
            await session.execute(stmt)
        
        await session.commit()
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))

async def check_upcoming_expirations():
    """Проверяет подписки, истекающие через 1 или 2 дня и уведомляет пользователей."""
    async with async_session() as session:
        now = datetime.utcnow()

        # Временные границы
        tomorrow = now + timedelta(days=1)
        day_after_tomorrow = now + timedelta(days=2)

        stmt = select(User).where(
            User.is_active == True,
            User.subscription_end.in_([tomorrow.date(), day_after_tomorrow.date()])
        )

        result = await session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            days_left = (user.subscription_end.date() - now.date()).days
            if days_left == 2:
                message = (
                    "⚠️ Ваша подписка истекает через 2 дня!\n\n"
                )
            elif days_left == 1:
                message = (
                    "⚠️ Ваша подписка истекает завтра!\n\n"
                )
            else:
                continue  # На всякий случай

            try:
                await bot.send_message(user.telegram_id, message, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
                                                            [
                                                                [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
                                                            ]))
            except Exception as e:
                print(f"Error sending message to user {user.telegram_id}: {e}")

def start_scheduler():
    """Запускает планировщик"""
    # Проверяем истекшие подписки каждый день в полночь
    scheduler.add_job(
        check_expired_subscriptions,
        CronTrigger(hour=0, minute=0),
        id='check_subscriptions',
        replace_existing=True
    )
    
    # Проверяем подписки, которые скоро истекают, каждый день в 12:00
    scheduler.add_job(
        check_upcoming_expirations,
        CronTrigger(hour=12, minute=0),
        id='check_upcoming_expirations',
        replace_existing=True
    )
    
    scheduler.start() 