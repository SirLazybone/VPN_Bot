from aiogram import Router, types, F
from aiogram.types import LabeledPrice
from config.config import PAYMENT_TOKEN, DONATE_STREAM_URL, ADMIN_CHAT, VPN_PRICE, TECH_SUPPORT_USERNAME
from fastapi import FastAPI, Request, Response
from db.database import async_session
from db.models import User
from db.service.payment_service import create_payment, get_user_payments, get_payment_by_payment_id, \
    update_payment_status
from db.service.user_service import get_or_create_user, get_user_by_username, update_user_balance, \
    renew_subscription
from bot.vpn_manager import VPNManager
from fastapi import APIRouter, Request
import json
from datetime import datetime, timedelta
import traceback
import logging
import asyncio
from sheets.sheets_service import update_payment_by_nickname, update_user_by_telegram_id
from bot.donate_api import DonateApi
from sqlalchemy import select

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
webhook_router = APIRouter()


class MockUser:
    def __init__(self, id, username):
        self.id = int(id)  # Ensure the ID is an integer
        self.username = username


@router.callback_query(F.data == "payment")
async def process_payment(callback: types.CallbackQuery, bot):
    # Сразу отвечаем пользователю, чтобы показать что запрос обрабатывается
    await callback.answer("Создаем платеж...")
    
    # Показываем промежуточное сообщение
    loading_message = await callback.message.edit_text(
        "⏳ Создаем платеж...\n"
        "Это может занять несколько секунд",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[
                types.InlineKeyboardButton(text="🏠 Отмена", callback_data="home")
            ]]
        )
    )
    
    try:
        async with async_session() as session:
            # Быстро создаем пользователя и платеж
            user = await get_or_create_user(session, callback.from_user)
            payment = await create_payment(
                session=session,
                user_id=user.id,
                nickname=user.username
            )
            
            # Обновляем сообщение
            await loading_message.edit_text(
                "⏳ Создаем ссылку для оплаты...\n"
                "Подключаемся к платежной системе...",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(text="🏠 Отмена", callback_data="home")
                    ]]
                )
            )
            
            donate_api = DonateApi()
            response = await donate_api.create_donate_url(payment_id=payment.id)
            
            if response is None:
                await loading_message.edit_text(
                    "❌ Не удалось создать ссылку для платежа\n\n"
                    "Проблема с платежной системой. Попробуйте снова через некоторое время",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [types.InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="payment")],
                            [types.InlineKeyboardButton(text="❓ Поддержка", url=f"https://t.me/{TECH_SUPPORT_USERNAME}")],
                            [types.InlineKeyboardButton(text="🏠 Домой", callback_data="home")]
                        ]
                    )
                )
                return

            # Обновляем статус платежа в БД
            await update_payment_status(
                session=session, 
                id=payment.id, 
                payment_id=response['id'],
                status=response['status'], 
                amount=response['amount']
            )

            # Создаем финальную клавиатуру
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="💳 Оплатить",
                            url=response['url'],
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="✅ Проверить оплату",
                            callback_data=f"check_payment:{payment.payment_id}"
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text='❓ Поддержка',
                            url=f'https://t.me/{TECH_SUPPORT_USERNAME}'
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="🏠 Домой",
                            callback_data='home'
                        )
                    ]
                ]
            )
            
            # Финальное сообщение с результатом
            await loading_message.edit_text(
                f"✅ Платеж создан!\n\n"
                f"📌 Что нужно сделать:\n"
                "1️⃣ Перейдите по ссылке «Оплатить»\n"
                "2️⃣ Оплатите по СБП\n"
                "3️⃣ Вернитесь в бота и нажмите «Проверить оплату»",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        try:
            await loading_message.edit_text(
                "❌ Произошла ошибка при создании платежа\n\n"
                "Попробуйте еще раз или обратитесь в поддержку",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="payment")],
                        [types.InlineKeyboardButton(text="❓ Поддержка", url=f"https://t.me/{TECH_SUPPORT_USERNAME}")],
                        [types.InlineKeyboardButton(text="🏠 Домой", callback_data="home")]
                    ]
                )
            )
        except Exception as edit_error:
            logger.error(f"Ошибка при редактировании сообщения об ошибке: {edit_error}")
            # В крайнем случае отправляем новое сообщение
            await callback.message.answer(
                "❌ Произошла ошибка при создании платежа. Попробуйте еще раз.",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="🏠 Домой", callback_data="home")]]
                )
            )


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(callback: types.CallbackQuery):
    """
    Проверяет оплату и продлевает подписку
    """
    payment_id = callback.data.split(":")[1]
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        payment = await get_payment_by_payment_id(session, payment_id)

        donate_api = DonateApi()
        response = await donate_api.find_donate_url(payment_id)

        if response is None:
            await callback.answer(text="Что-то пошло не так...\n"
                                       "Создайте новый платёж", show_alert=True)
            return

        if response['status'] == 'Time':
            await callback.answer(
                "Проверка оплаты...\n"
                "Если вы уже оплатили, но статус не обновился, подождите несколько минут и попробуйте снова.",
                show_alert=True
            )
            return

        if not payment:
            await callback.answer("Платёж не создался, попробуйте заново", show_alert=True)
            return

        if payment.user_id != user.id:
            await callback.answer("Этот платёж не принадлежит вам.", show_alert=True)
            return

        now = datetime.utcnow()
        dt = datetime.strptime(response['expirationDateTime'], "%Y-%m-%dT%H:%M:%S.%fZ")

        if dt < now:
            await callback.answer("Время на оплату истекло, создайте новый платёж", show_alert=True)
            return

        if response['status'] == 'Closed':
            await update_user_balance(session, username=user.username, amount=float(response['amount']))
            await update_payment_status(session, id=payment.id, status=response['status'])

            success = await renew_subscription(session, user.id, 30)

            if success:
                # Обновляем VPN конфигурацию
                vpn_manager = VPNManager(session)
                success_2 = await vpn_manager.renew_subscription(
                    user=user,
                    subscription_days=30
                )

                if success_2:
                    # Получаем обновленного пользователя из базы
                    updated_user_result = await session.execute(select(User).where(User.id == user.id))
                    updated_user = updated_user_result.scalar_one_or_none()
                    
                    if updated_user and updated_user.vpn_link:
                        message_text = (f"✅ Подписка успешно продлена!\n\n"
                                        f"Ваша подписка активна до: {updated_user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                                        f"Ваша VPN конфигурация:\n\n"
                                        f"```\n{updated_user.vpn_link}\n```\n\n")
                    else:
                        message_text = (f"✅ Подписка успешно продлена!\n\n"
                                        f"Ваша подписка активна до: {user.subscription_end.strftime('%d.%m.%Y')}\n\n"
                                        f"❌ Не удалось получить VPN конфигурацию. Попробуйте позже.")
                else:
                    message_text = ("❌ Ошибка при создании VPN конфигурации.\n"
                                    "Пожалуйста, попробуйте продлить подписку в главном меню")
                    # Возвращаем деньги, так как VPN не создался
                    user.balance += VPN_PRICE

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
                await callback.message.answer(text=message_text, reply_markup=success_keyboard, parse_mode="Markdown")
            else:
                await callback.answer("Недостаточно средств на балансе для продления подписки", show_alert=True)
        else:
            await callback.answer(
                "Проверка оплаты...\n"
                "Если вы уже оплатили, но статус не обновился, подождите несколько минут и попробуйте снова.",
                show_alert=True
            )

