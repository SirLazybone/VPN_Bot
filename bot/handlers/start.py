from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.service.user_service import get_or_create_user, is_user_exist, get_user_by_telegram_id, renew_subscription
from config.config import CHANNEL_ID, CHANNEL_USERNAME, TECH_SUPPORT_USERNAME
from bot.utils import check_subscription
from bot.handlers.home import process_home_action
from db.database import async_session
from bot.handlers.home import home_callback
from bot.vpn_manager import VPNManager
from aiogram import Bot
from config.config import BOT_TOKEN, VPN_PRICE_REF, DAYS_FOR_REF
import asyncio

router = Router()
bot = Bot(BOT_TOKEN)

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot):
    async with async_session() as session:
        if await is_user_exist(session, message.from_user.id):
            if await check_subscription(message.from_user.id, bot):
                await process_home_action(message)
                return

    text = message.text or ""
    parts = text.split()
    referrer_id = None

    if len(parts) > 1:
        referrer_id = parts[1]
        if referrer_id.isdigit() and int(referrer_id) != message.from_user.id:
            referrer_id = int(referrer_id)

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
                    callback_data=f"check_subscription_{referrer_id}"
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

@router.callback_query(F.data.startswith("check_subscription_"))
async def check_subscription_callback(callback: types.CallbackQuery, bot):
    # Получаем данные из callback
    parts = callback.data.split("_")
    if parts[2] != 'None' and parts[2].isdigit():
        referrer_id = int(parts[2])
    else:
        referrer_id = None

    await callback.answer("⏳ Проверяем подписку...")
            
    await callback.message.edit_text(
        "🔧 Проверяем вашу подписку...\n\n"
        "⏳ Пожалуйста, подождите несколько секунд"
    )

    # if referrer_id is not None:
    #     await asyncio.sleep(2)
    
    # Проверяем подписку
    if not await check_subscription(callback.from_user.id, bot):
        await callback.answer(
            "❌ Вы еще не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True
        )
        return

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user)

    # Показываем интерфейс выбора устройства
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
    
    await callback.message.edit_text(
        "🎉 Поздравляем с регистрацией!\n"
        "💰 Вы получили месяц бесплатного использования!\n\n"
        "👇 Выберите свое устройство и начните пользоваться VPN",
        reply_markup=keyboard2
    )
    await callback.answer()

    # ТОЛЬКО ПОСЛЕ отправки ответа пользователю запускаем фоновую задачу для рефера
    if referrer_id is not None:
        asyncio.create_task(
            process_referrer_vpn_renewal_isolated(
                referrer_id, 
                callback.from_user.username or "пользователь"
            )
        )
        print(f"🚀 Запущена фоновая задача VPN продления для рефера ID: {referrer_id}")

async def process_referrer_vpn_renewal_isolated(referrer_id: int, new_user_username: str):
    """
    ПОЛНОСТЬЮ ИЗОЛИРОВАННАЯ фоновая задача для продления VPN подписки рефера.
    Работает в отдельной сессии и не влияет на основной поток.
    """
    # Даем основному потоку время полностью завершиться
    # await asyncio.sleep(2)
    
    # Создаем ОТДЕЛЬНЫЙ Bot объект для фоновых операций
    background_bot = None
    try:
        from aiogram import Bot
        from config.config import BOT_TOKEN
        background_bot = Bot(BOT_TOKEN)
        
        # Создаем ОТДЕЛЬНУЮ сессию для фоновой задачи
        async with async_session() as isolated_session:
            # Получаем актуальные данные рефера
            referrer_user = await get_user_by_telegram_id(isolated_session, referrer_id)
            if not referrer_user:
                print(f"❌ Рефер с ID {referrer_id} не найден")
                return
            
            # Сохраняем текущее состояние на случай отката
            was_active = referrer_user.is_active
            old_sub_end = referrer_user.subscription_end
            
            # Обновляем подписку в базе данных (быстро)
            success = await renew_subscription(isolated_session, referrer_user.id, days=DAYS_FOR_REF, price=0)
            
            if success:
                # Создаем VPN менеджер с ИЗОЛИРОВАННОЙ сессией
                vpn_manager = VPNManager(isolated_session)
                
                # Пытаемся продлить VPN подписку
                success_vpn = await vpn_manager.renew_subscription(user=referrer_user, subscription_days=DAYS_FOR_REF)
                
                if success_vpn:
                    # Отправляем уведомление об успешном продлении
                    await background_bot.send_message(
                        referrer_user.telegram_id,
                        f"🎉 Пользователь @{new_user_username} успешно зарегистрировался!\n"
                        f"✅ Ваша подписка продлена на {DAYS_FOR_REF} дней"
                    )
                    # print(f"✅ VPN подписка рефера @{referrer_user.username} успешно продлена")
                else:
                    # Если VPN API недоступен, откатываем изменения и начисляем бонус на баланс
                    referrer_user.is_active = was_active
                    referrer_user.subscription_end = old_sub_end
                    referrer_user.balance += VPN_PRICE_REF
                    await isolated_session.commit()
                    
                    await background_bot.send_message(
                        referrer_user.telegram_id,
                        f"🎉 Пользователь @{new_user_username} успешно зарегистрировался!\n"
                        f"⚠️ К сожалению, сейчас проблемы с VPN серверами\n"
                        f"🔄 Попробуйте продлить подписку позже через меню \"Продлить подписку\""
                    )
                    print(f"⚠️ VPN API недоступен для рефера @{referrer_user.username}, начислен бонус на баланс")
            else:
                print(f"❌ Не удалось обновить подписку рефера @{referrer_user.username} в базе данных")
                
    except Exception as e:
        print(f"❌ Ошибка при обработке VPN продления для рефера {referrer_id}: {e}")
        
        # Пытаемся уведомить рефера об ошибке (если bot создался)
        if background_bot:
            try:
                await background_bot.send_message(
                    referrer_id,
                    f"🎉 Пользователь @{new_user_username} успешно зарегистрировался!\n"
                    f"⚠️ Произошла техническая ошибка при продлении VPN\n"
                    f"🔧 Обратитесь в поддержку для решения вопроса"
                )
            except Exception as notify_error:
                print(f"❌ Не удалось уведомить рефера об ошибке: {notify_error}")
    finally:
        # ОБЯЗАТЕЛЬНО закрываем отдельный Bot объект
        if background_bot:
            try:
                await background_bot.session.close()
            except Exception as close_error:
                print(f"❌ Ошибка при закрытии background_bot: {close_error}")
