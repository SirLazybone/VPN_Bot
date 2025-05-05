from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.database import async_session
from db.service.user_service import get_or_create_user
from config.config import TECH_SUPPORT_USERNAME
from datetime import datetime
from db.service.user_service import renew_subscription
from bot.vpn_manager import VPNManager
router = Router()

@router.callback_query(F.data == 'home')
async def home_callback(callback: types.CallbackGame):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Мои сервера', callback_data='configs')],
            [InlineKeyboardButton(text='Обновить', callback_data='home')],
            [InlineKeyboardButton(text='Пополнить баланс', callback_data='payment')],
            [InlineKeyboardButton(text='Продлить подписку', callback_data='update_sub')],
            [InlineKeyboardButton(text='Поддержка', url=f'https://t.me/{TECH_SUPPORT_USERNAME}')],
        ]
    )
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
    await callback.message.edit_text(f"Привет {user.username}!\n"
                                    f"Ваш баланс: {user.balance} руб.\n"
                                    f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y') if user.subscription_end else 'Нет активной подписки'}\n", 
                                    reply_markup=keyboard) 
        

@router.callback_query(F.data == "configs")
async def configs_callback(callback: types.CallbackQuery):
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
            f"{user.vpn_link}\n\n"
            f"Подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}"
        )
        await callback.answer() 

@router.callback_query(F.data == "update_sub")
async def update_subscription(callback: types.CallbackQuery):
    """Продлевает подписку за счет баланса"""
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        
        success = await renew_subscription(session, user.id, 30)
        
        if success:
            # Обновляем VPN конфигурацию
            vpn_manager = VPNManager(session)
            vpn_link = await vpn_manager.renew_subscription(
                user=user,
                subscription_days=30
            )
            
            if vpn_link:
                await callback.message.edit_text(
                    "✅ Подписка успешно продлена!\n\n"
                    f"Ваша подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                    f"Ваш баланс: {user.balance} руб.\n\n"
                    f"Ваша VPN конфигурация:\n{vpn_link}",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text="Домой",
                                    callback_data="home"
                                )
                            ]
                        ]
                    )
                )
            else:
                await callback.message.edit_text(
                    "❌ Ошибка при обновлении VPN конфигурации.\n"
                    "Пожалуйста, свяжитесь с поддержкой."
                )
        else:
            await callback.message.edit_text(
                "❌ Недостаточно средств на балансе.\n"
                f"Текущий баланс: {user.balance} руб.\n"
                "Необходимо: 149 руб.\n\n"
                "Пожалуйста, пополните баланс.",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="💳 Пополнить баланс",
                                callback_data="payment"
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text="Домой",
                                callback_data="home"
                            )
                        ]
                    ]
                )
            )
        
        await callback.answer() 