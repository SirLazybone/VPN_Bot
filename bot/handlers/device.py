from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db.database import async_session
from db.service.user_service import get_or_create_user, get_user_by_username
from bot.vpn_manager import VPNManager
from config.config import TECH_SUPPORT_USERNAME
from typing import Optional
import asyncio

router = Router()


async def process_vpn_config(
        callback: types.CallbackQuery,
        platform: str,
        instruction_url: Optional[str] = None
) -> None:
    """
    Обработчик создания и отображения VPN конфигурации для различных платформ

    :param callback: Объект callback-запроса
    :param platform: Платформа
    :param instruction_url: Необязательная ссылка на инструкцию
    """
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)

        keyboard_buttons = []

        if instruction_url:
            keyboard_buttons.append([
                InlineKeyboardButton(text="📕 Инструкция", url=instruction_url)
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="🏠 Домой", callback_data="home_first")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        if user.vpn_link:
            await callback.message.edit_text(
                f"🔑 Ваша VPN конфигурация:\n\n"
                f"```\n{user.vpn_link}\n```\n\n"
                f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n"
                "Нажмите на конфигурации для копирования",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Показываем временное сообщение о создании конфигурации
        await callback.answer("⏳ Создаем VPN конфигурацию...")
        
        await callback.message.edit_text(
            "🔧 Создаем вашу VPN конфигурацию...\n\n"
            "⏳ Пожалуйста, подождите несколько секунд"
        )

        vpn_manager = VPNManager(session)
        vpn_link = await vpn_manager.create_vpn_config(
            user=user,
            subscription_days=14
        )

        if vpn_link:
            await callback.message.edit_text(
                f"```\n{user.vpn_link}\n```\n\n"
                f"🔐 Ваш ключ готов! Скопируйте его нажатием и вставьте в соответствии с инструкцией.\n\n"
                f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при создании VPN конфигурации.\n"
                "Попробуйте чуть позже в разделе \"Мои ключи\"\n",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=callback.data)],
                    [InlineKeyboardButton(text="🏠 Домой", callback_data='home_first')],
                ])
            )


@router.callback_query(F.data == "ios")
async def ios_config(callback: types.CallbackQuery):
    await process_vpn_config(
        callback,
        platform="iOS",
        instruction_url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr"
    )


@router.callback_query(F.data == "android")
async def android_config(callback: types.CallbackQuery):
    await process_vpn_config(
        callback,
        platform="Android",
        instruction_url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr"
    )


@router.callback_query(F.data == "windows")
async def windows_config(callback: types.CallbackQuery):
    await process_vpn_config(
        callback,
        platform="Windows",
        instruction_url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr"
    )


@router.callback_query(F.data == "macos")
async def windows_config(callback: types.CallbackQuery):
    await process_vpn_config(
        callback,
        platform="MacOS",
        instruction_url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr"
    )

