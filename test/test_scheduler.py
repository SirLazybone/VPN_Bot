from db.database import async_session
from datetime import timedelta, datetime
from sqlalchemy import func, select, or_, and_
from db.models import User
from aiogram import Bot, types
from config.config import BOT_TOKEN
from bot.scheduler import check_upcoming_expirations, check_expired_subscriptions
import asyncio

bot = Bot(BOT_TOKEN)
async def test_sql():
    await check_upcoming_expirations()
    await check_expired_subscriptions()

    async with async_session() as session:
        now = datetime.utcnow()
        tomorrow_start = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        tomorrow_end = datetime.combine(now.date() + timedelta(days=1), datetime.max.time())

        day_after_start = datetime.combine(now.date() + timedelta(days=2), datetime.min.time())
        day_after_end = datetime.combine(now.date() + timedelta(days=2), datetime.max.time())

        result = await session.execute(select(User).where(
            User.is_active == True,
            or_(
                and_(
                    User.subscription_end >= tomorrow_start,
                    User.subscription_end <= tomorrow_end
                ),
                and_(
                    User.subscription_end >= day_after_start,
                    User.subscription_end <= day_after_end
                )
            )
        ))
        users = result.scalars().all()

        for user in users:
            print('Скоро истекает:')
            print(user.username)
            await bot.send_message(
                user.telegram_id,
                "⚠️ Ваша скоро истекла!\n\n",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
                                                        [
                                                            [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
                                                        ])
            )

    now = datetime.utcnow()
    stmt = select(User).where(
        User.subscription_end < now,
        User.is_active == True
    )
    result = await session.execute(stmt)
    expired_users = result.scalars().all()

    for user in expired_users:
        print("Уже истекла:")
        print(user.username)
        await bot.send_message(
            user.telegram_id,
            "⚠️ Ваша подписка истекла!\n\n",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
            [
                [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
            ])
        )

    await session.close()
    await bot.close()

if __name__ == '__main__':
    asyncio.run(test_sql())