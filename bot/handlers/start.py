from aiogram import Router, types, F
from aiogram.filters import Command
from db.service.user_service import get_or_create_user
from config.config import CHANNEL_ID, CHANNEL_USERNAME
from bot.utils import check_subscription
from db.database import async_session

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                )
            ]
        ]
    )
    
    await message.answer(
        "Добро пожаловать!\n\n"
        "Для использования бота необходимо подписаться на наш канал:\n"
        f"https://t.me/{CHANNEL_USERNAME}\n\n"
        "После подписки нажмите кнопку ниже для проверки:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery, bot):
    if await check_subscription(callback.from_user.id, bot):
        async with async_session() as session:
            user = await get_or_create_user(session, callback.from_user)

        keyboard2 = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="IOS",
                        callback_data="ios"
                    ),
                    types.InlineKeyboardButton(
                        text="Android",
                        callback_data="android"
                    )
                ]
            ]
        )
        # keyboard = types.InlineKeyboardMarkup(
        #     inline_keyboard=[
        #         [
        #             types.InlineKeyboardButton(
        #                 text="💳 Оплатить VPN",
        #                 callback_data="payment"
        #             )
        #         ],
        #         [
        #             types.InlineKeyboardButton(
        #                 text="🔑 Получить конфигурацию",
        #                 callback_data="get_vpn"
        #             )
        #         ]
        #     ]
        # )
        
        await callback.message.edit_text(
            "✅ Отлично! Вы успешно подписаны на канал!\n\n"
            "Поздравляем с регистрацией! Вам начислены 149 рублей на баланс.\n\n"
            "Выберите действие:",
            reply_markup=keyboard2
        )
    else:
        await callback.answer(
            "❌ Вы еще не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True
        )

