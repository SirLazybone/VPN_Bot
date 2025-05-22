from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from db.database import async_session
from db.service.user_service import get_or_create_user
from config.config import TECH_SUPPORT_USERNAME, VPN_PRICE
from datetime import datetime
from db.service.user_service import renew_subscription
from bot.vpn_manager import VPNManager
router = Router()


async def process_home_action(event):
    """
    Общая функция обработки home-действия
    Работает как с Message, так и с CallbackQuery
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔑 Мои ключи', callback_data='configs')],
            [InlineKeyboardButton(text='💳 Продлить подписку', callback_data='update_sub')],
            [InlineKeyboardButton(text='🔄 Обновить', callback_data='home')],
            [InlineKeyboardButton(text='❓Поддержка', url=f'https://t.me/{TECH_SUPPORT_USERNAME}')],
        ]
    )

    async with async_session() as session:
        # Определяем пользователя в зависимости от типа события
        if isinstance(event, types.Message):
            user = await get_or_create_user(session, event.from_user)
            message_to_edit = await event.answer(
                f"👋 Привет {user.username}!\n\n"
                f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y') if user.subscription_end else 'Нет активной подписки'}\n",
                reply_markup=keyboard
            )
        else:  # CallbackQuery
            user = await get_or_create_user(session, event.from_user)
            await event.message.edit_text(
                f"👋Привет {user.username}!\n"
                f"💰Ваш баланс: {user.balance} руб.\n"
                f"📅Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y') if user.subscription_end else 'Нет активной подписки'}\n",
                reply_markup=keyboard
            )

        # Если это callback, вызываем answer
        if isinstance(event, types.CallbackQuery):
            await event.answer()


@router.message(Command("home"))
async def home_command(message: types.Message):
    await process_home_action(message)


@router.callback_query(F.data == 'home')
async def home_callback(callback: types.CallbackQuery):
    await process_home_action(callback)


@router.callback_query(F.data == "configs")
async def configs_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📕 Инструкция", url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr")],
        [InlineKeyboardButton(text="🏠 Домой", callback_data='home')]
    ])
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        
        if not user.vpn_link:
            await callback.message.answer(
                "❌ У вас ещё нет VPN конфигурации.\n"
                "Пожалуйста, оплатите подписку для получения конфигурации."
            )
            await callback.answer()
            return

        if not user.is_active or not user.subscription_end or user.subscription_end < datetime.utcnow():
            await callback.message.answer(
                "❌ Ваша подписка неактивна или истекла.\n"
                "Пожалуйста, продлите подписку для использования VPN."
            )
            await callback.answer()
            return

        await callback.message.answer(
            f"🔑 Ваша VPN конфигурация:\n\n"
            f"```\n{user.vpn_link}\n```\n\n"
            f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n"
            "Нажмите на конфигурации для копирования",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer() 


async def process_update_sub_action(event):
    """
    Общая функция обработки update_sub действия
    Работает как с Message, так и с CallbackQuery
    """
    async with async_session() as session:
        if isinstance(event, types.Message):
            user = await get_or_create_user(session, event.from_user)
        else: 
            user = await get_or_create_user(session, event.from_user)

        success = await renew_subscription(session, user.id, 30)

        if success:
            # Обновляем VPN конфигурацию
            vpn_manager = VPNManager(session)
            vpn_link = await vpn_manager.renew_subscription(
                user=user,
                subscription_days=30
            )

            message_text = (
                "✅ Подписка успешно продлена!\n\n"
                f"Ваша подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                f"Ваш баланс: {user.balance} руб.\n\n"
                f"Ваша VPN конфигурация:\n\n"
                f"```\n{user.vpn_link}\n```\n\n",

            ) if vpn_link else (
                "❌ Ошибка при обновлении VPN конфигурации.\n"
                "Пожалуйста, свяжитесь с поддержкой."
            )

            success_keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🏠 Домой",
                            callback_data="home"
                        )
                    ]
                ]
            )
        else:
            message_text = (
                "❌ Недостаточно средств на балансе.\n"
                f"💵 Необходимо: {VPN_PRICE} руб.\n\n"
                "⚠️ Пожалуйста, пополните баланс, чтобы продлить подписку."
            )
            
            error_keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="💳 Пополнить баланс",
                            callback_data="payment"
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="🏠 Домой",
                            callback_data="home"
                        )
                    ]
                ]
            )

        # Отправляем или редактируем сообщение в зависимости от типа события
        if isinstance(event, types.Message):
            await event.answer(
                message_text,
                reply_markup=success_keyboard if success and vpn_link else error_keyboard,
                parse_mode="Markdown"
            )
        else:  # CallbackQuery
            await event.message.edit_text(
                message_text,
                reply_markup=success_keyboard if success and vpn_link else error_keyboard,
                parse_mode="Markdown"
            )
            await event.answer()


@router.message(Command("update_sub"))
async def update_sub_command(message: types.Message):
    await process_update_sub_action(message)


@router.callback_query(F.data == "update_sub")
async def update_subscription(callback: types.CallbackQuery):
    await process_update_sub_action(callback)
