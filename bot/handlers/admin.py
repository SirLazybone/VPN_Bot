from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete
from datetime import datetime, timezone
from db.database import async_session
from db.models import User, Payment
from bot.handlers.home import process_home_action
from bot.vpn_manager import VPNManager
from sheets.sheets import update_user_by_telegram_id
from config.config import ADMIN_NAME_1, ADMIN_NAME_2
import asyncio

router = Router()
ADMINS = [ADMIN_NAME_1, ADMIN_NAME_2]

# FSM states for admin actions
class AdminStates(StatesGroup):
    search_user = State()
    edit_balance = State()
    edit_subscription = State()
    confirm_delete = State()

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
        text += f"Статус: {'✅ Активен' if user.is_active else '❌ Неактивен'}\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user.id}_{page}")
                ],
                [
                    types.InlineKeyboardButton(text="📅 Изменить подписку", callback_data=f"admin_edit_subscription_{user.id}_{page}")
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
        text += f"Статус: {'✅ Активен' if user.is_active else '❌ Неактивен'}\n"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user.id}")
                ],
                [
                    types.InlineKeyboardButton(text="📅 Изменить подписку", callback_data=f"admin_edit_subscription_{user.id}")
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
        await vpn_manager.renew_subscription(user=user, new_expire_ts=int(new_date.timestamp()))
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))
        await session.commit()

        await state.clear()
        
        formatted_date = new_date.strftime("%d.%m.%Y %H:%M")
        await message.answer(
            f"Дата окончания подписки пользователя @{user.username} успешно изменена на {formatted_date}",
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
        if await vpn_manager.delete_user(username):
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