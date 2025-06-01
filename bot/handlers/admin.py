from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from sqlalchemy import select, delete
from datetime import datetime, timezone
from db.database import async_session
from db.models import User, Payment, Server
from bot.handlers.home import process_home_action
from bot.vpn_manager import VPNManager
from sheets.sheets import update_user_by_telegram_id
from config.config import ADMIN_NAME_1, ADMIN_NAME_2, BOT_TOKEN
from db.service.server_service import (
    get_all_servers, get_server_by_id, create_server, 
    update_server, set_default_server, delete_server, get_default_server,
    get_servers_statistics, get_server_users_count, get_server_active_users_count
)
import asyncio

router = Router()
bot = Bot(token=BOT_TOKEN)
ADMINS = [ADMIN_NAME_1, ADMIN_NAME_2]

# FSM states for admin actions
class AdminStates(StatesGroup):
    search_user = State()
    edit_balance = State()
    edit_subscription = State()
    confirm_delete = State()
    mail_everyone = State()
    mail_user = State()
    mail_type_choice = State()
    mail_photo = State()
    mail_photo_text = State()
    
    # Новые состояния для управления серверами
    add_server_name = State()
    add_server_url = State()
    add_server_description = State()
    edit_server_name = State()
    edit_server_url = State()
    edit_server_description = State()
    confirm_delete_server = State()

@router.message(F.text == "admin")
async def admin_handler(message: types.Message):
    if message.from_user.username not in ADMINS:
        await process_home_action(message)
        return
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_list_users")
            ],
            [
                types.InlineKeyboardButton(text="🔍 Поиск по имени", callback_data="admin_search_user")
            ],
            [
                types.InlineKeyboardButton(text="🖥️ Управление серверами", callback_data="admin_servers")
            ],
            [
                types.InlineKeyboardButton(text="✉️ Отправить сообщение всем пользователям", callback_data="init_mailing")
            ],
            [
                types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")
            ]
        ]
    )
    
    await message.answer("👑 Панель администратора", reply_markup=keyboard)

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await process_home_action(callback)
        return
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_list_users")
            ],
            [
                types.InlineKeyboardButton(text="🔍 Поиск по имени", callback_data="admin_search_user")
            ],
            [
                types.InlineKeyboardButton(text="🖥️ Управление серверами", callback_data="admin_servers")
            ],
            [
                types.InlineKeyboardButton(text="✉️ Отправить сообщение всем пользователям", callback_data="init_mailing")
            ],
            [
                types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")
            ]
        ]
    )
    
    await callback.message.edit_text("👑 Панель администратора", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_list_users")
async def list_users(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    # Redirect to first page
    await list_users_page(callback, page=1)

@router.callback_query(F.data.startswith("admin_list_users_page_"))
async def list_users_page(callback: types.CallbackQuery, page: int = None):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    # Extract page number from callback data if not provided
    if page is None:
        page = int(callback.data.split("_")[4])
    
    users_per_page = 10
    offset = (page - 1) * users_per_page
    
    async with async_session() as session:
        # Get total count of users
        count_result = await session.execute(select(User))
        total_users = len(count_result.scalars().all())
        
        # Get users for current page
        result = await session.execute(
            select(User).order_by(User.id).offset(offset).limit(users_per_page)
        )
        users = result.scalars().all()
        
        if not users and page == 1:
            await callback.message.edit_text(
                "Пользователей не найдено",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await callback.answer()
            return
        
        # Calculate total pages
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        # Create text with page info
        text = f"📋 Список пользователей (страница {page}/{total_pages}):\n"
        text += f"Всего пользователей: {total_users}\n\n"
        
        # Create keyboard with users in 2 columns
        keyboard = []
        
        # Add users in rows of 2
        for i in range(0, len(users), 2):
            row = []
            # First user in row
            user1 = users[i]
            status1 = "✅" if user1.is_active else "❌"
            row.append(types.InlineKeyboardButton(
                text=f"{status1} {user1.username or f'ID{user1.id}'}",
                callback_data=f"admin_user_{user1.id}_{page}"
            ))
            
            # Second user in row (if exists)
            if i + 1 < len(users):
                user2 = users[i + 1]
                status2 = "✅" if user2.is_active else "❌"
                row.append(types.InlineKeyboardButton(
                    text=f"{status2} {user2.username or f'ID{user2.id}'}",
                    callback_data=f"admin_user_{user2.id}_{page}"
                ))
            
            keyboard.append(row)
        
        # Add navigation buttons
        navigation_row = []
        
        # Previous page button
        if page > 1:
            navigation_row.append(types.InlineKeyboardButton(
                text="◀️ Пред.",
                callback_data=f"admin_list_users_page_{page - 1}"
            ))
        
        # Next page button
        if page < total_pages:
            navigation_row.append(types.InlineKeyboardButton(
                text="След. ▶️",
                callback_data=f"admin_list_users_page_{page + 1}"
            ))
        
        if navigation_row:
            keyboard.append(navigation_row)
        
        # Add back button
        keyboard.append([types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

@router.callback_query(F.data.startswith("admin_user_"))
async def show_user_details(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    # Extract user_id and optional page from callback data
    parts = callback.data.split("_")
    user_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.edit_text(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_list_users_page_{page}")]]
                )
            )
            await callback.answer()
            return
        
        # Format subscription dates
        sub_start = user.subscription_start.strftime("%d.%m.%Y %H:%M") if user.subscription_start else "Не установлено"
        sub_end = user.subscription_end.strftime("%d.%m.%Y %H:%M") if user.subscription_end else "Не установлено"
        
        text = f"👤 Информация о пользователе:\n\n"
        text += f"ID: {user.id}\n"
        text += f"Telegram ID: {user.telegram_id}\n"
        text += f"Username: @{user.username}\n"
        text += f"Баланс: {user.balance} руб.\n"
        text += f"Подписка с: {sub_start}\n"
        text += f"Подписка до: {sub_end}\n"
        text += f"Сервер: {user.server_id if user.server_id else 'Не назначен'}\n"
        text += f"Статус: {'✅ Активен' if user.is_active else '❌ Неактивен'}\n"
        text += f"Пробный период: {'🎯 Использован' if user.trial_used else '⭕ Не использован'}\n"
        text += f"VPN конфиг: {'✅ Есть' if user.vpn_link else '❌ Нет'}\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user.id}_{page}")
                ],
                [
                    types.InlineKeyboardButton(text="📅 Изменить подписку", callback_data=f"admin_edit_subscription_{user.id}_{page}")
                ],
                [
                    types.InlineKeyboardButton(text="✉️ Написать", callback_data=f"mail_user_{user.id}_{page}")
                ],
                [
                    types.InlineKeyboardButton(text="❌ Удалить пользователя", callback_data=f"admin_delete_user_{user.id}_{page}")
                ],
                [
                    types.InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_list_users_page_{page}")
                ]
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

@router.callback_query(F.data == "admin_search_user")
async def search_user_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.search_user)
    
    await callback.message.edit_text(
        "Введите имя пользователя:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
        )
    )
    await callback.answer()

@router.message(AdminStates.search_user)
async def search_user_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return

    username = message.text.strip()

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            return
        
        # Reset state
        await state.clear()
        
        # Show user details
        sub_start = user.subscription_start.strftime("%d.%m.%Y %H:%M") if user.subscription_start else "Не установлено"
        sub_end = user.subscription_end.strftime("%d.%m.%Y %H:%M") if user.subscription_end else "Не установлено"
        
        text = f"👤 Информация о пользователе:\n\n"
        text += f"ID: {user.id}\n"
        text += f"Telegram ID: {user.telegram_id}\n"
        text += f"Username: @{user.username}\n"
        text += f"Баланс: {user.balance} руб.\n"
        text += f"Подписка с: {sub_start}\n"
        text += f"Подписка до: {sub_end}\n"
        text += f"Сервер: {user.server_id if user.server_id else 'Не назначен'}\n"
        text += f"Статус: {'✅ Активен' if user.is_active else '❌ Неактивен'}\n"
        text += f"Пробный период: {'🎯 Использован' if user.trial_used else '⭕ Не использован'}\n"
        text += f"VPN конфиг: {'✅ Есть' if user.vpn_link else '❌ Нет'}\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user.id}")
                ],
                [
                    types.InlineKeyboardButton(text="📅 Изменить подписку", callback_data=f"admin_edit_subscription_{user.id}")
                ],
                [
                    types.InlineKeyboardButton(text="✉️ Написать", callback_data=f"mail_user_{user.id}")
                ],
                [
                    types.InlineKeyboardButton(text="❌ Удалить пользователя", callback_data=f"admin_delete_user_{user.id}")
                ],
                [
                    types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
                ]
            ]
        )
        
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_edit_balance_"))
async def edit_balance_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 1
    
    await state.update_data(user_id=user_id, page=page)
    await state.set_state(AdminStates.edit_balance)
    
    await callback.message.edit_text(
        "Введите новый баланс пользователя:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin_user_{user_id}_{page}")]]
        )
    )
    await callback.answer()

@router.message(AdminStates.edit_balance)
async def edit_balance_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return
    
    try:
        new_balance = float(message.text.strip())
    except ValueError:
        await message.answer(
            "Некорректное значение. Пожалуйста, введите числовое значение:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
            )
        )
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    page = data.get("page", 1)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await state.clear()
            return
        
        user.balance = new_balance
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
        await session.commit()
        
        await state.clear()
        
        await message.answer(
            f"Баланс пользователя @{user.username} успешно изменен на {new_balance} руб.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ К пользователю", callback_data=f"admin_user_{user_id}_{page}")]]
            )
        )

@router.callback_query(F.data.startswith("admin_edit_subscription_"))
async def edit_subscription_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 1
    
    await state.update_data(user_id=user_id, page=page)
    await state.set_state(AdminStates.edit_subscription)
    
    await callback.message.edit_text(
        "Введите новую дату окончания подписки в формате ДД.ММ.ГГГГ:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin_user_{user_id}_{page}")]]
        )
    )
    await callback.answer()

@router.message(AdminStates.edit_subscription)
async def edit_subscription_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return
    
    try:
        # Parse date in format DD.MM.YYYY
        date_str = message.text.strip()
        day, month, year = map(int, date_str.split('.'))
        new_date = datetime(year, month, day, 23, 59, 59)
    except (ValueError, IndexError):
        await message.answer(
            "Некорректный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
            )
        )
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    page = data.get("page", 1)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await state.clear()
            return
        
        # If no subscription_start, set it to now
        if not user.subscription_start:
            user.subscription_start = datetime.utcnow()
        
        user.subscription_end = new_date
        user.is_active = True  # Activate user when setting subscription

        vpn_manager = VPNManager(session)
        vpn_success = await vpn_manager.renew_subscription(user=user, new_expire_ts=int(new_date.timestamp()))
        
        if vpn_success:
            # Получаем обновленного пользователя для получения актуальной VPN ссылки
            await session.refresh(user)
            
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
        await session.commit()

        await state.clear()
        
        formatted_date = new_date.strftime("%d.%m.%Y %H:%M")
        
        if vpn_success:
            success_message = f"✅ Дата окончания подписки пользователя @{user.username} успешно изменена на {formatted_date}"
            if user.vpn_link:
                success_message += "\n🔐 VPN конфигурация обновлена"
        else:
            success_message = f"⚠️ Дата подписки изменена на {formatted_date}, но возникла ошибка с VPN конфигурацией"
        
        await message.answer(
            success_message,
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ К пользователю", callback_data=f"admin_user_{user_id}_{page}")]]
            )
        )

@router.callback_query(F.data.startswith("admin_delete_user_"))
async def delete_user_confirm(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 1
    
    await state.update_data(user_id=user_id, page=page)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.edit_text(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await callback.answer()
            return
        
        await state.set_state(AdminStates.confirm_delete)
        
        await callback.message.edit_text(
            f"⚠️ Вы уверены, что хотите удалить пользователя @{user.username} (ID: {user.id})?",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_confirm_delete_{user.id}_{page}")
                    ],
                    [
                        types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_{user.id}_{page}")
                    ]
                ]
            )
        )
        await callback.answer()

@router.callback_query(F.data.startswith("admin_confirm_delete_"))
async def delete_user_process(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    page = int(parts[4]) if len(parts) > 4 else 1
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        
        if not user:
            await callback.message.edit_text(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await callback.answer()
            await state.clear()
            return
        
        # Remember username for confirmation message
        username = user.username
        
        # Delete user
        await session.execute(delete(Payment).where(Payment.nickname == username))
        await session.execute(delete(User).where(User.id == user_id))
        vpn_manager = VPNManager(session)
        text = ""
        if await vpn_manager.delete_user(username, server_id=user.server_id):
            text = "Пользователь успешно удалён на сервере"
        else:
            text = "Не удалось удалить пользователя на сервере"
        await session.commit()
        
        await state.clear()
        
        await callback.message.edit_text(
            f"Пользователь @{username} успешно удален в боте\n" + text,
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ К списку пользователей", callback_data=f"admin_list_users_page_{page}")]]
            )
        )
        await callback.answer()


@router.callback_query(F.data == "init_mailing")
async def init_mail_everyone(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.mail_type_choice)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="📝 Только текст", callback_data="mail_text_only")
            ],
            [
                types.InlineKeyboardButton(text="🖼️ Текст с картинкой", callback_data="mail_with_photo")
            ],
            [
                types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")
            ]
        ]
    )

    await callback.message.edit_text(
        "Выберите тип сообщения для рассылки:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.message(AdminStates.mail_everyone)
async def mail_everyone(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        await message.answer("Доступ запрещен", show_alert=True)
        return

    mail = message.text

    await state.clear()

    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        success_count = 0
        error_count = 0

        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    text=mail
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"Error sending message to user {user.username}: {e}")

        await message.answer(
            f"Текстовое сообщение отправлено!\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {error_count}",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
            )
        )


@router.callback_query(F.data.startswith("mail_user_"))
async def init_mail_user(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1

    await state.set_state(AdminStates.mail_user)
    await state.update_data(user_id=user_id, page=page)

    await callback.message.edit_text(
        "Введите сообщение для пользователя:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin_user_{user_id}_{page}")]]
        )
    )
    await callback.answer()

@router.message(AdminStates.mail_user)
async def mail_user(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        await message.answer("Доступ запрещен", show_alert=True)
        return

    mail = message.text
    data = await state.get_data()
    user_id = data.get("user_id")
    page = data.get("page")

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                "Пользователь не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
                )
            )
            await state.clear()
            return

        try:
            await bot.send_message(
                user.telegram_id,
                text=mail
            )
            await message.answer(f"Сообщение отправлено пользователю {user.username}",
                                 reply_markup=types.InlineKeyboardMarkup(
                                     inline_keyboard=[[types.InlineKeyboardButton(text="◀️ К пользователю",
                                                                                  callback_data=f"admin_user_{user_id}_{page}")]]
                                 ))
            await state.clear()
        except Exception as e:
            await message.answer(f"Error sending message to user {user.username}: {e}")

@router.callback_query(F.data == "mail_text_only")
async def mail_text_only(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.mail_everyone)

    await callback.message.edit_text(
        "Введите текст сообщения:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
        )
    )
    await callback.answer()


@router.callback_query(F.data == "mail_with_photo")
async def mail_with_photo_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.mail_photo)

    await callback.message.edit_text(
        "Отправьте картинку:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
        )
    )
    await callback.answer()


@router.message(AdminStates.mail_photo, F.photo)
async def handle_mail_photo(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return

    # Сохраняем file_id картинки
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await state.set_state(AdminStates.mail_photo_text)

    await message.answer(
        "Теперь введите текст для сообщения с картинкой:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_panel")]]
        )
    )


@router.message(AdminStates.mail_photo_text)
async def mail_photo_with_text(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        await message.answer("Доступ запрещен", show_alert=True)
        return

    text = message.text
    data = await state.get_data()
    photo_file_id = data.get("photo_file_id")

    await state.clear()

    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        success_count = 0
        error_count = 0

        for user in users:
            try:
                await bot.send_photo(
                    user.telegram_id,
                    photo=photo_file_id,
                    caption=text
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"Error sending message to user {user.username}: {e}")

        await message.answer(
            f"Сообщение с картинкой отправлено!\n"
            f"Успешно: {success_count}\n"
            f"Ошибок: {error_count}",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]]
            )
        )


# ======================== УПРАВЛЕНИЕ СЕРВЕРАМИ ========================

@router.callback_query(F.data == "admin_servers")
async def admin_servers_menu(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    async with async_session() as session:
        stats = await get_servers_statistics(session)
        default_server = await get_default_server(session)
        
        text = "🖥️ Управление серверами\n\n"
        
        if stats["total_servers"] == 0:
            text += "📭 Серверы не настроены\n"
            text += "Используется fallback конфигурация из .env"
        else:
            text += f"📊 Всего серверов: {stats['total_servers']}\n"
            text += f"✅ Активных: {stats['active_servers']}\n\n"
            
            for server_data in stats["servers_data"]:
                status = "✅" if server_data["is_active"] else "❌"
                default_mark = " 🎯" if default_server and server_data["id"] == default_server.id else ""
                
                text += f"{status} {server_data['name']}{default_mark}\n"
                text += f"   ID: {server_data['id']} | URL: {server_data['url'][:30]}...\n"
                text += f"   👥 Всего: {server_data['total_users']} | Активных: {server_data['active_users']}\n"
                
                if server_data["description"]:
                    text += f"   📝 {server_data['description']}\n"
                text += "\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server")
                ],
                [
                    types.InlineKeyboardButton(text="📋 Список серверов", callback_data="list_servers")
                ],
                [
                    types.InlineKeyboardButton(text="🎯 Сменить активный", callback_data="change_default_server")
                ],
                [
                    types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
                ]
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

@router.callback_query(F.data == "list_servers")
async def list_servers_menu(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    async with async_session() as session:
        servers = await get_all_servers(session)
        
        if not servers:
            await callback.message.edit_text(
                "📭 Серверы не настроены",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers")]]
                )
            )
            await callback.answer()
            return
        
        # Создаем кнопки для серверов
        keyboard = []
        for server in servers:
            status = "✅" if server.is_active else "❌"
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{status} {server.name}",
                    callback_data=f"server_details_{server.id}"
                )
            ])
        
        keyboard.append([types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers")])
        
        await callback.message.edit_text(
            "📋 Выберите сервер для управления:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

@router.callback_query(F.data.startswith("server_details_"))
async def server_details(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    server_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        server = await get_server_by_id(session, server_id)
        default_server = await get_default_server(session)
        
        if not server:
            await callback.message.edit_text(
                "❌ Сервер не найден",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="list_servers")]]
                )
            )
            await callback.answer()
            return
        
        # Подсчитываем пользователей на сервере через новые функции
        total_users = await get_server_users_count(session, server_id)
        active_users = await get_server_active_users_count(session, server_id)
        
        is_default = default_server and server.id == default_server.id
        status = "✅ Активен" if server.is_active else "❌ Неактивен"
        default_text = " (По умолчанию)" if is_default else ""
        
        text = f"🖥️ Сервер: {server.name}{default_text}\n\n"
        text += f"ID: {server.id}\n"
        text += f"URL: {server.url}\n"
        text += f"Статус: {status}\n"
        text += f"👥 Всего пользователей: {total_users}\n"
        text += f"🖥️ Активных на VPN: {active_users}\n"
        text += f"📅 Создан: {server.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if server.description:
            text += f"\n📝 Описание:\n{server.description}"
        
        keyboard = []
        
        # Кнопка активации/деактивации
        if server.is_active:
            keyboard.append([types.InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"toggle_server_{server_id}")])
        else:
            keyboard.append([types.InlineKeyboardButton(text="✅ Активировать", callback_data=f"toggle_server_{server_id}")])
        
        # Кнопка установки по умолчанию
        if not is_default and server.is_active:
            keyboard.append([types.InlineKeyboardButton(text="🎯 Сделать основным", callback_data=f"set_default_{server_id}")])
        
        keyboard.extend([
            [types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_server_{server_id}")],
            [types.InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_server_{server_id}")],
            [types.InlineKeyboardButton(text="◀️ Назад", callback_data="list_servers")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

@router.callback_query(F.data == "add_server")
async def add_server_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.add_server_name)
    
    await callback.message.edit_text(
        "➕ Добавление нового сервера\n\n"
        "Введите название сервера:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_servers")]]
        )
    )
    await callback.answer()

@router.message(AdminStates.add_server_name)
async def add_server_name_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return
    
    server_name = message.text.strip()
    if not server_name:
        await message.answer("❌ Название не может быть пустым. Попробуйте еще раз:")
        return
    
    await state.update_data(server_name=server_name)
    await state.set_state(AdminStates.add_server_url)
    
    await message.answer(
        f"Название: {server_name}\n\n"
        "Теперь введите URL API сервера (например: https://example.com):",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_servers")]]
        )
    )

@router.message(AdminStates.add_server_url)
async def add_server_url_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return
    
    server_url = message.text.strip()
    if not server_url.startswith(('http://', 'https://')):
        await message.answer("❌ URL должен начинаться с http:// или https://. Попробуйте еще раз:")
        return
    
    await state.update_data(server_url=server_url)
    await state.set_state(AdminStates.add_server_description)
    
    data = await state.get_data()
    await message.answer(
        f"Название: {data['server_name']}\n"
        f"URL: {server_url}\n\n"
        "Введите описание сервера (или отправьте '-' чтобы пропустить):",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_servers")]]
        )
    )

@router.message(AdminStates.add_server_description)
async def add_server_description_process(message: types.Message, state: FSMContext):
    if message.from_user.username not in ADMINS:
        return
    
    description = message.text.strip()
    if description == '-':
        description = None
    
    data = await state.get_data()
    
    async with async_session() as session:
        try:
            server = await create_server(
                session=session,
                name=data['server_name'],
                url=data['server_url'],
                description=description
            )
            
            await state.clear()
            
            await message.answer(
                f"✅ Сервер успешно добавлен!\n\n"
                f"Название: {server.name}\n"
                f"URL: {server.url}\n"
                f"ID: {server.id}",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ К серверам", callback_data="admin_servers")]]
                )
            )
            
        except Exception as e:
            await message.answer(
                f"❌ Ошибка при создании сервера: {e}",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers")]]
                )
            )
            await state.clear()

@router.callback_query(F.data.startswith("toggle_server_"))
async def toggle_server_status(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    server_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        server = await get_server_by_id(session, server_id)
        if not server:
            await callback.answer("❌ Сервер не найден", show_alert=True)
            return
        
        new_status = not server.is_active
        success = await update_server(session, server_id, is_active=new_status)
        
        if success:
            status_text = "активирован" if new_status else "деактивирован"
            await callback.answer(f"✅ Сервер {status_text}")
            # Обновляем детали сервера
            await server_details(callback)
        else:
            await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)

@router.callback_query(F.data.startswith("set_default_"))
async def set_default_server_handler(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    server_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        success = await set_default_server(session, server_id)
        
        if success:
            await callback.answer("✅ Сервер установлен как основной")
            # Обновляем детали сервера
            await server_details(callback)
        else:
            await callback.answer("❌ Ошибка при установке сервера", show_alert=True)

@router.callback_query(F.data == "change_default_server")
async def change_default_server_menu(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMINS:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    async with async_session() as session:
        servers = await get_all_servers(session)
        active_servers = [s for s in servers if s.is_active]
        default_server = await get_default_server(session)
        
        if not active_servers:
            await callback.message.edit_text(
                "❌ Нет активных серверов",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers")]]
                )
            )
            await callback.answer()
            return
        
        text = "🎯 Выберите сервер для новых пользователей:\n\n"
        keyboard = []
        
        for server in active_servers:
            is_current = default_server and server.id == default_server.id
            text_prefix = "🎯 " if is_current else "   "
            keyboard.append([
                types.InlineKeyboardButton(
                    text=f"{text_prefix}{server.name}",
                    callback_data=f"set_default_{server.id}"
                )
            ])
        
        keyboard.append([types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers")])
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

