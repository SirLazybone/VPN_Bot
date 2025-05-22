from aiogram import Router, types, F
from aiogram.types import LabeledPrice
from config.config import PAYMENT_TOKEN, DONATE_STREAM_URL, ADMIN_CHAT, VPN_PRICE
from fastapi import FastAPI, Request, Response
from db.database import async_session
from db.service.payment_service import create_payment, get_user_payments, get_payment_by_id
from db.service.user_service import get_or_create_user, get_user_by_username
from bot.vpn_manager import VPNManager
from fastapi import APIRouter, Request
import json
from datetime import datetime
import traceback
import logging
import asyncio
from sheets.sheets import update_payment_by_nickname, update_user_by_telegram_id


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
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)

        # Создаем новый платеж
        payment = await create_payment(
            session=session,
            user_id=user.id,
            nickname=user.username
        )

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="💳 Оплатить",
                        url=DONATE_STREAM_URL,
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="✅ Проверить оплату",
                        callback_data=f"check_payment:{payment.id}"
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
        await callback.message.edit_text(
            f"💳 Платеж создан!\n\n"
            f"❗️ВАШ НИКНЕЙМ: ```{user.username}```\n\n"
            f"📌 Что нужно сделать:\n"
            "1️⃣ Скопируйте ваш ник выше\n"
            "2️⃣ Перейдите по ссылке «Оплатить»\n"
            "3️⃣ Вставьте скопированный никнейм в поле\n"
            "4️⃣ Оплатите банковской картой\n"
            "5️⃣ Вернитесь в бота и нажмите «Проверить оплату»\n",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await callback.answer()


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(callback: types.CallbackQuery):
    """
    Проверяет оплату и продлевает подписку
    """
    id = int(callback.data.split(":")[1])
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)
        payment = await get_payment_by_id(session, id)

        if not payment:
            await callback.answer("Платёж не создался, попробуйте заново", show_alert=True)
            return

        if payment.user_id != user.id:
            await callback.answer("Этот платёж не принадлежит вам.", show_alert=True)
            return

        if payment.status == 'completed':
            await callback.message.edit_text(
                "✅ Оплата подтверждена!\n\n"
                f"Ваш баланс: {user.balance}\n\n",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="🏠 Домой",
                                callback_data="home"
                            )
                        ]
                    ]
                )
            )
        else:
            await callback.answer(
                "Проверка оплаты...\n"
                "Если вы уже оплатили, но статус не обновился, подождите несколько минут и попробуйте снова.",
                show_alert=True
            )


@webhook_router.post("/donate")
async def donate_webhook(request: Request):
    async with async_session() as session:
        try:
            logger.info("Starting webhook processing...")
            data = await request.json()
            logger.info(f"Received webhook data: {data}")

            # Обрабатываем подтверждение вебхука
            if "type" in data and data.get("type") == "confirm":
                logger.info("Processing confirm webhook")
                return Response(content="eatHy5mWJ1", status_code=200)

            # Обрабатываем донат
            if "sum" in data:
                logger.info("Processing donation...")
                nickname = data.get('nickname')
                if not nickname:
                    logger.error("No nickname provided in donation data")
                    return Response(content="No nickname provided", status_code=400)

                logger.info(f"Looking for user with username: {nickname}")
                user = await get_user_by_username(session, nickname)

                if not user:
                    logger.error(f"User with username {nickname} not found")
                    return Response(content=f"User {nickname} not found", status_code=404)

                logger.info(f"User found: {user.id}, {user.username}")

                payments = await get_user_payments(session, user.id)

                if not payments:
                    logger.error("No pending payment found for user")
                    return Response(content="No pending payment found", status_code=404)

                payment = payments[0]

                if payment.status != 'pending':
                    logger.error("No pending payment found for user")
                    return Response(content="No pending payment found", status_code=404)

                payment.status = 'completed'
                payment.amount = float(data.get('sum'))
                payment.payment_id = data.get('uid')
                payment.completed_at = datetime.utcnow()
                payment.message = data.get('message')
                payment.pay_system = data.get('pay_system')

                user.balance += float(data.get('sum'))

                await session.commit()

                await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
                await asyncio.gather(update_payment_by_nickname(nickname, payment))

                logger.info("Webhook processing completed successfully")
                return Response(content="OK", status_code=200)

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            logger.error("Traceback:")
            logger.error(traceback.format_exc())
            return Response(content=str(e), status_code=500)
