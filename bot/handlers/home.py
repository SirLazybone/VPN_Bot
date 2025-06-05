from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from db.database import async_session
from db.service.user_service import get_or_create_user
from config.config import TECH_SUPPORT_USERNAME, VPN_PRICE, VPN_PRICE_3, VPN_PRICE_6
from datetime import datetime
from db.service.user_service import renew_subscription, is_user_exist
from bot.vpn_manager import VPNManager
from sheets.sheets_service import update_user_by_telegram_id
router = Router()


async def process_home_action(event):
    """
    Общая функция обработки home-действия
    Работает как с Message, так и с CallbackQuery
    """
    async with async_session() as session:
        if not await is_user_exist(session, event.from_user.id):
            return
        await session.close()
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
        
        if (not user.vpn_link and not user.trial_used) or (not user.vpn_link and user.subscription_end and user.subscription_end > datetime.utcnow()):
            vpn_manager = VPNManager(session)
            if user.subscription_end and user.subscription_end > datetime.utcnow():
                subscription_days = (user.subscription_end - datetime.utcnow()).days
            else:
                subscription_days = 30
            vpn_link = await vpn_manager.create_vpn_config(
                user=user,
                subscription_days=subscription_days
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
            await update_user_by_telegram_id(telegram_id=user.telegram_id, user=user)
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


@router.callback_query(F.data == "update_sub")
async def update_subscription_auto(callback: types.CallbackQuery):
    """
    Автоматически определяет период подписки по балансу пользователя
    """
        
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        
        # Определяем максимальный период, который можно купить на текущий баланс
        if user.balance >= VPN_PRICE_6:
            period_months = 6
            price = VPN_PRICE_6
            period_text = "6 месяцев"
        elif user.balance >= VPN_PRICE_3:
            period_months = 3 
            price = VPN_PRICE_3
            period_text = "3 месяца"
        elif user.balance >= VPN_PRICE:
            period_months = 1
            price = VPN_PRICE
            period_text = "1 месяц"
        else:
            # Недостаточно средств даже на 1 месяц
            await callback.message.edit_text(
                f"❌ Недостаточно средств на балансе.\n\n"
                "⚠️ Пожалуйста, пополните баланс для продления подписки.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="💳 Пополнить баланс",
                                callback_data="payment"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="🏠 Домой",
                                callback_data="home"
                            )
                        ]
                    ]
                )
            )
            await callback.answer()
            return
        
        # Показываем что будет продлено и просим подтверждения
        confirm_text = f"💳 Продление подписки\n\n"
        confirm_text += f"📅 Период: {period_text}\n"
        confirm_text += "Подтвердите продление подписки:"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"✅ Продлить на {period_text}",
                        callback_data=f"confirm_sub_{period_months}_{price}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="home"
                    )
                ]
            ]
        )
        
        await callback.message.edit_text(confirm_text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(F.data.startswith("confirm_sub_"))
async def confirm_subscription(callback: types.CallbackQuery):
    """
    Подтверждает и обрабатывает продление подписки
    """
    # Извлекаем период и цену из callback_data
    parts = callback.data.split("_")
    period_months = int(parts[2])
    price = float(parts[3])
    
    await process_update_sub_action(callback, period_months, price)


async def process_update_sub_action(event, period_months, price):
    """
    Обрабатывает продление подписки на выбранный период
    """
    async with async_session() as session:
        if isinstance(event, types.Message):
            user = await get_or_create_user(session, event.from_user)
        else: 
            user = await get_or_create_user(session, event.from_user)

        # Списываем деньги и продлеваем подписку
        old_sub_end = user.subscription_end
        success = await renew_subscription(session, user.id, period_months * 30, price)

        if success:
            # Пытаемся создать/обновить VPN конфигурацию
            vpn_manager = VPNManager(session)
            vpn_success = await vpn_manager.renew_subscription(
                user=user,
                subscription_days=period_months * 30
            )

            if vpn_success:
                # Получаем обновленного пользователя из базы
                await session.refresh(user)
                
                if user.vpn_link:
                    message_text = (
                        "✅ Подписка успешно продлена!\n\n"
                        f"📅 Период: {period_months} мес.\n"
                        f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                        f"Ваша VPN конфигурация:\n\n"
                        f"```\n{user.vpn_link}\n```"
                    )
                else:
                    message_text = (
                        "✅ Подписка продлена!\n\n"
                        f"📅 Период: {period_months} мес.\n"
                        f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                        "❌ Не удалось получить VPN конфигурацию. Попробуйте позже в разделе 'Мои ключи'."
                    )
                
                success_keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="🔑 Мои ключи",
                                callback_data="configs"
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
                # VPN не создался - возвращаем деньги
                user.balance += price
                user.subscription_end = old_sub_end
                await session.commit()
                
                message_text = (
                    "❌ Ошибка при создании VPN конфигурации.\n\n"
                    f"💰 Деньги возвращены на баланс: {price} ₽.\n"
                    "Пожалуйста, попробуйте позже или свяжитесь с поддержкой."
                )
                
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
                                text="❓ Поддержка",
                                url=f'https://t.me/{TECH_SUPPORT_USERNAME}'
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
            # Не удалось продлить подписку - возвращаемся к выбору
            message_text = (
                "❌ Произошла ошибка при продлении подписки.\n\n"
                "Пожалуйста, попробуйте еще раз или обратитесь в поддержку."
            )
            
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
                            text="❓ Поддержка",
                            url=f'https://t.me/{TECH_SUPPORT_USERNAME}'
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


# @router.message(Command("update_sub"))
# async def update_sub_command(message: types.Message):
#     await process_update_sub_action(message)



