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
            [InlineKeyboardButton(text='🔄 Обновить', callback_data='home_new')],
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
                f"👋 Привет {user.username}!\n\n"
                f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y') if user.subscription_end else 'Нет активной подписки'}\n",
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

@router.callback_query(F.data == 'home_new')
async def new_home_message(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔑 Мои ключи', callback_data='configs')],
            [InlineKeyboardButton(text='💳 Продлить подписку', callback_data='update_sub')],
            [InlineKeyboardButton(text='🔄 Обновить', callback_data='home_new')],
            [InlineKeyboardButton(text='❓Поддержка', url=f'https://t.me/{TECH_SUPPORT_USERNAME}')],
        ]
    )
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        await callback.message.answer(
            f"👋 Привет {user.username}!\n\n"
            f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y') if user.subscription_end else 'Нет активной подписки'}\n",
            reply_markup=keyboard
        )


@router.callback_query(F.data == "configs")
async def configs_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📕 Инструкция", url="https://teletype.in/@meowadmin/Z4Z0lCMlWWr")],
        [InlineKeyboardButton(text="🏠 Домой", callback_data='home')]
    ])
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        
        if not user.vpn_link and not user.trial_used:
            vpn_manager = VPNManager(session)
            vpn_link = await vpn_manager.create_vpn_config(
                user=user,
                subscription_days=30
            )
            if not vpn_link:
                await callback.message.edit_text(
                    "❌ Ошибка при создании VPN конфигурации.\n"
                    "Попробуйте чуть позже в разделе \"Мои ключи\"\n"
                    "Если не получится, свяжитесь с поддержкой.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Домой", callback_data='home')],
                        [InlineKeyboardButton(text="Техподдержка", url=f'https://t.me/{TECH_SUPPORT_USERNAME}')]
                    ])
                )
            else:
                await callback.message.edit_text(
                    f"```\n{user.vpn_link}\n```\n\n"
                    f"🔐 Ваш ключ готов! Скопируйте его нажатием и вставьте в соответствии с инструкцией.\n\n"
                    f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            await callback.answer()
            return

        if not user.is_active or not user.subscription_end or user.subscription_end < datetime.utcnow():
            await callback.message.answer(
                "❌ Ваша подписка неактивна или истекла.\n"
                "Пожалуйста, продлите подписку для использования VPN.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Продлить подписку', callback_data='update_sub')]
                ])
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            f"```\n{user.vpn_link}\n```\n\n"
            f"🔐 Ваш ключ готов! Скопируйте его нажатием и вставьте в соответствии с инструкцией.\n\n"
            f"📅 Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}",
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
            # Обновляем VPN конфигурацию или создаем новую
            vpn_manager = VPNManager(session)
            vpn_success = await vpn_manager.renew_subscription(
                user=user,
                subscription_days=30
            )

            if vpn_success:
                # Получаем обновленного пользователя из базы
                await session.refresh(user)
                
                if user.vpn_link:
                    message_text = (
                        "✅ Подписка успешно продлена!\n\n"
                        f"Ваша подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                        f"Ваша VPN конфигурация:\n\n"
                        f"```\n{user.vpn_link}\n```\n\n"
                    )
                else:
                    message_text = (
                        "✅ Подписка продлена!\n\n"
                        f"Ваша подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                        "❌ Не удалось получить VPN конфигурацию. Попробуйте позже."
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
                    "❌ Ошибка при создании VPN конфигурации.\n"
                    "Пожалуйста, попробуйте позже или свяжитесь с поддержкой."
                )
                
                # Возвращаем деньги, так как VPN не создался
                user.balance += VPN_PRICE
                await session.commit()
                
                success_keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="🔄 Попробовать снова",
                                callback_data="update_sub"
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
        else:
            message_text = (
                "❌ Недостаточно средств на балансе.\n"
                f"💵 Необходимо: {VPN_PRICE} руб.\n\n"
                "⚠️ Пожалуйста, пополните баланс, чтобы продлить подписку."
            )
            
            success_keyboard = types.InlineKeyboardMarkup(
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
                reply_markup=success_keyboard,
                parse_mode="Markdown"
            )
        else:  # CallbackQuery
            await event.message.edit_text(
                message_text,
                reply_markup=success_keyboard,
                parse_mode="Markdown"
            )
            await event.answer()


@router.message(Command("update_sub"))
async def update_sub_command(message: types.Message):
    await process_update_sub_action(message)


@router.callback_query(F.data == "update_sub")
async def update_subscription(callback: types.CallbackQuery):
    await process_update_sub_action(callback)
