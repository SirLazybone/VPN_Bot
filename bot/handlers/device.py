from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db.database import async_session
from db.service.user_service import get_or_create_user, get_user_by_username
from bot.vpn_manager import VPNManager
from config.config import TECH_SUPPORT_USERNAME

router = Router()


@router.callback_query(F.data == "ios")
async def ios_config(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Домой", callback_data="home")]
        ])
        
        if user.vpn_link:
            await callback.message.edit_text(
                f"🔑 Ваша VPN конфигурация для iOS:\n\n"
                f"{user.vpn_link}\n\n"
                f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}",
                reply_markup=keyboard
            )
            await callback.answer()
            return

        vpn_manager = VPNManager(session)
        vpn_link = await vpn_manager.create_vpn_config(
            user=user,
            subscription_days=30
        )

        if vpn_link:
            await callback.message.edit_text(
                f"🔑 Ваша VPN конфигурация для iOS:\n\n"
                f"{vpn_link}\n\n"
                f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                "Спасибо за регистрацию! Вам предоставлен пробный период на 30 дней.",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при создании VPN конфигурации.\n"
                "Пожалуйста, свяжитесь с поддержкой.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Техподдержка", url=f'https://t.me/{TECH_SUPPORT_USERNAME}')]
                ])
            )
        
        await callback.answer()


@router.callback_query(F.data == "android")
async def android_config(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Домой", callback_data="home")]
        ])
        
        if user.vpn_link:
            await callback.message.edit_text(
                f"🔑 Ваша VPN конфигурация для Android:\n\n"
                f"{user.vpn_link}\n\n"
                f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}",
                reply_markup=keyboard
            )
            await callback.answer()
            return

        vpn_manager = VPNManager(session)
        vpn_link = await vpn_manager.create_vpn_config(
            user=user,
            subscription_days=30 
        )

        if vpn_link:
            await callback.message.edit_text(
                f"🔑 Ваша VPN конфигурация для Android:\n\n"
                f"{vpn_link}\n\n"
                f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                "Спасибо за регистрацию! Вам предоставлен пробный период на 30 дней.",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при создании VPN конфигурации.\n"
                "Пожалуйста, свяжитесь с поддержкой.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Техподдержка", url=f'https://t.me/{TECH_SUPPORT_USERNAME}')]
                ])
            )
        
        await callback.answer()
