from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.service.user_service import get_or_create_user, is_user_exist
from config.config import CHANNEL_ID, CHANNEL_USERNAME, TECH_SUPPORT_USERNAME
from bot.utils import check_subscription
from bot.handlers.home import process_home_action
from db.database import async_session
from bot.handlers.home import home_callback

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot):
    async with async_session() as session:
        if await is_user_exist(session, message.from_user.id):
            if await check_subscription(message.from_user.id, bot):
                await process_home_action(message)
                return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Наш канал",
                    url=f"https://t.me/{CHANNEL_USERNAME}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                )
            ]
        ]
    )
    
    await message.answer(
        "🐱  Meow VPN — это твой билет в безопасный интернет!\n"
        "🚀 Скорость до 1 Гбит/с : больше никаких ожиданий загрузки!\n"
        "💰 Первый месяц бесплатно! \n\n"
        "Для использования нашего сервиса - подпишитесь на канал",
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
                ],
                [
                    types.InlineKeyboardButton(
                        text="Windows",
                        callback_data="windows"
                    ),
                    types.InlineKeyboardButton(
                        text="MacOS",
                        callback_data="macos"
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
            "🎉 Поздравляем с регистрацией!\n"
            "💰 Вы получили месяц бесплатного использования!\n\n"
            "👇 Выберите свое устройство и начните пользоваться VPN",
            reply_markup=keyboard2
        )
    else:
        await callback.answer(
            "❌ Вы еще не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True
        )

