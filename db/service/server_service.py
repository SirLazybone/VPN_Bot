from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from db.models import Server, User
from typing import List, Optional
from datetime import datetime, timedelta
from config.config import VPN_PRICE, BOT_TOKEN, ADMIN_NAME_1, ADMIN_NAME_2
from aiogram import Bot
import asyncio

ADMINS = [ADMIN_NAME_1, ADMIN_NAME_2]

async def get_all_servers(session: AsyncSession) -> List[Server]:
    """Получить все серверы"""
    result = await session.execute(select(Server).order_by(Server.id))
    return result.scalars().all()

async def get_active_servers(session: AsyncSession) -> List[Server]:
    """Получить только активные серверы"""
    result = await session.execute(
        select(Server).where(Server.is_active == True).order_by(Server.id)
    )
    return result.scalars().all()

async def get_server_by_id(session: AsyncSession, server_id: int) -> Optional[Server]:
    """Получить сервер по ID"""
    result = await session.execute(select(Server).where(Server.id == server_id))
    return result.scalar_one_or_none()

async def get_server_with_users(session: AsyncSession, server_id: int) -> Optional[Server]:
    """Получить сервер со всеми его пользователями"""
    result = await session.execute(
        select(Server)
        .options(selectinload(Server.users))
        .where(Server.id == server_id)
    )
    return result.scalar_one_or_none()

async def get_server_users_count(session: AsyncSession, server_id: int) -> int:
    """Получить количество пользователей на сервере"""
    result = await session.execute(
        select(User).where(User.server_id == server_id)
    )
    return len(result.scalars().all())

async def get_server_active_users_count(session: AsyncSession, server_id: int) -> int:
    """Получить количество активных пользователей на сервере (с VPN конфигами)"""
    result = await session.execute(
        select(User).where(
            User.server_id == server_id,
            User.vpn_link.isnot(None)
        )
    )
    return len(result.scalars().all())

async def get_default_server(session: AsyncSession) -> Optional[Server]:
    """Получить сервер по умолчанию"""
    result = await session.execute(
        select(Server).where(Server.is_default == True, Server.is_active == True)
    )
    server_fin = result.scalar_one_or_none()
    
    # Если нет сервера по умолчанию, возвращаем с наименьшим количеством пользователей активный
    if not server_fin:
        result = await session.execute(select(Server).where(Server.is_active == True))
        servers = result.scalars().all()
        min_users = int(1e10)
        for server in servers:
            users_count = await get_server_users_count(session, server.id)
            if users_count < min_users:
                min_users = users_count
                server_fin = server
    return server_fin

async def create_server(
    session: AsyncSession, 
    name: str, 
    url: str, 
    description: str = None,
    is_active: bool = True
) -> Server:
    """Создать новый сервер"""
    server = Server(
        name=name,
        url=url,
        description=description,
        is_active=is_active,
        is_default=False
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server

async def update_server(
    session: AsyncSession,
    server_id: int,
    name: str = None,
    url: str = None,
    description: str = None,
    is_active: bool = None
) -> bool:
    """Обновить сервер"""
    update_data = {}
    if name is not None:
        update_data[Server.name] = name
    if url is not None:
        update_data[Server.url] = url
    if description is not None:
        update_data[Server.description] = description
    if is_active is not None:
        update_data[Server.is_active] = is_active
    
    if not update_data:
        return False
    
    result = await session.execute(
        update(Server).where(Server.id == server_id).values(**update_data)
    )
    await session.commit()
    return result.rowcount > 0

async def set_default_server(session: AsyncSession, server_id: int) -> bool:
    """Установить сервер как сервер по умолчанию"""
    # Сначала убираем флаг is_default у всех серверов
    await session.execute(update(Server).values(is_default=False))
    
    # Устанавливаем флаг для выбранного сервера
    result = await session.execute(
        update(Server).where(Server.id == server_id).values(is_default=True)
    )
    await session.commit()
    return result.rowcount > 0

async def delete_server(session: AsyncSession, server_id: int) -> bool:
    """Удалить сервер (только если на нем нет пользователей)"""
    # Проверяем, есть ли пользователи на этом сервере
    users_result = await session.execute(
        select(User).where(User.server_id == server_id).limit(1)
    )
    if users_result.scalar_one_or_none():
        return False  # Нельзя удалить сервер с пользователями
    
    server = await get_server_by_id(session, server_id)
    if server:
        await session.delete(server)
        await session.commit()
        return True
    return False

async def get_servers_count(session: AsyncSession) -> int:
    """Получить количество серверов"""
    result = await session.execute(select(Server))
    return len(result.scalars().all())

async def get_servers_statistics(session: AsyncSession) -> dict:
    """Получить статистику по всем серверам"""
    servers = await get_all_servers(session)
    stats = {
        "total_servers": len(servers),
        "active_servers": 0,
        "servers_data": []
    }
    
    for server in servers:
        if server.is_active:
            stats["active_servers"] += 1
        
        total_users = await get_server_users_count(session, server.id)
        active_users = await get_server_active_users_count(session, server.id)
        
        server_data = {
            "id": server.id,
            "name": server.name,
            "url": server.url,
            "is_active": server.is_active,
            "is_default": server.is_default,
            "total_users": total_users,
            "active_users": active_users,
            "description": server.description
        }
        stats["servers_data"].append(server_data)
    
    return stats

async def _create_vpn_configs_in_background(
    users_data: List[dict], 
    target_server_id: int, 
    source_server_name: str,
    target_server_name: str
):
    """
    Создает VPN конфигурации в фоновом режиме и отправляет уведомления пользователям
    """
    from bot.vpn_manager import VPNManager  # Импорт здесь чтобы избежать циклических импортов
    from db.database import async_session
    
    bot = Bot(token=BOT_TOKEN)
    success_count = 0
    error_count = 0
    
    try:
        async with async_session() as session:
            vpn_manager = VPNManager(session)
            
            for user_data in users_data:
                try:
                    # Получаем актуального пользователя из БД
                    result = await session.execute(
                        select(User).where(User.id == user_data['user_id'])
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        continue
                    
                    # Рассчитываем новую дату окончания подписки (исходная + 30 дней)
                    original_end = user_data['original_subscription_end']
                    extended_end = original_end + timedelta(days=30)
                    user.subscription_end = extended_end
                    
                    # Создаем новую VPN конфигурацию на целевом сервере с продленной подпиской
                    new_expire_ts = int(extended_end.timestamp())
                    vpn_success = await vpn_manager.renew_subscription(
                        user=user, 
                        new_expire_ts=new_expire_ts
                    )
                    
                    if vpn_success:
                        # Получаем обновленного пользователя для получения новой VPN ссылки
                        await session.refresh(user)
                        
                        # Отправляем уведомление с новой VPN ссылкой
                        message = (
                            f"✅ ВАША VPN КОНФИГУРАЦИЯ ВОССТАНОВЛЕНА!\n\n"
                            f"🔄 Ваш сервер '{source_server_name}' был недоступен, но мы автоматически создали новую конфигурацию на сервере '{target_server_name}'.\n\n"
                            f"🔗 Ваша новая VPN ссылка:\n"
                            f"```\n{user.vpn_link}\n```\n\n"
                            f"🎁 В качестве извинения мы продлили вашу подписку на 30 дней!\n"
                            f"⏰ Подписка теперь действует до: {extended_end.strftime('%d.%m.%Y %H:%M')}\n"
                            f"(было до: {original_end.strftime('%d.%m.%Y %H:%M')})\n\n"
                            f"✨ Просто скопируйте новую ссылку и используйте её вместо старой!"
                        )
                        
                        await bot.send_message(user.telegram_id, message, parse_mode='Markdown')
                        success_count += 1
                    else:
                        # Если не удалось создать VPN, отправляем сообщение с просьбой создать вручную
                        # Но подписка всё равно продлена
                        message = (
                            f"⚠️ ТРЕБУЕТСЯ ДЕЙСТВИЕ\n\n"
                            f"Ваш сервер '{source_server_name}' был недоступен. Мы переназначили вас на '{target_server_name}', но не смогли автоматически создать новую конфигурацию.\n\n"
                            f"📋 Что нужно сделать:\n"
                            f"• Создайте новую VPN конфигурацию в боте \'Мои ключи\'\n\n"
                            f"🎁 В качестве извинения мы продлили вашу подписку на 30 дней!\n"
                            f"⏰ Подписка теперь действует до: {extended_end.strftime('%d.%m.%Y %H:%M')}\n"
                            f"(было до: {original_end.strftime('%d.%m.%Y %H:%M')})\n\n"
                            f"Приносим извинения за неудобства! 🙏"
                        )
                        
                        await bot.send_message(user.telegram_id, message)
                        error_count += 1
                    
                    # Небольшая задержка между запросами
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"Ошибка при создании VPN для пользователя {user_data.get('username', 'Unknown')}: {e}")
                    error_count += 1
                    continue
                finally:
                    await session.commit()
        
        # Отправляем финальный отчет администраторам
        final_report = (
            f"🏁 ФИНАЛЬНЫЙ ОТЧЕТ ПО СОЗДАНИЮ VPN КОНФИГУРАЦИЙ\n\n"
            f"🔄 Переназначение с '{source_server_name}' на '{target_server_name}'\n\n"
            f"📊 Результаты создания VPN конфигураций:\n"
            f"✅ Успешно создано: {success_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"👥 Всего обработано: {len(users_data)}\n\n"
            f"🎁 Всем активным пользователям продлена подписка на 30 дней\n\n"
            f"🕐 Завершено: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')} UTC"
        )
        
        try:
            for admin in ADMINS:
                if admin:
                    try:
                        result = await session.execute(
                            select(User).where(User.username == admin.replace('@', ''))
                        )
                        admin_user = result.scalar_one_or_none()
                        await bot.send_message(admin_user.telegram_id, final_report)
                    except Exception as e:
                        print(f"Не удалось отправить отчет администратору {admin}: {e}")
        except Exception as e:
            print(f"Не удалось отправить финальный отчет: {e}")
            
    except Exception as e:
        error_report = (
            f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ СОЗДАНИИ VPN КОНФИГУРАЦИЙ\n\n"
            f"Переназначение с '{source_server_name}' на '{target_server_name}'\n"
            f"Ошибка: {str(e)}\n\n"
            f"🕐 Время: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')} UTC"
        )
        try:
            for admin in ADMINS:
                if admin:
                    try:
                        result = await session.execute(
                            select(User).where(User.username == admin.replace('@', ''))
                        )
                        admin_user = result.scalar_one_or_none()
                        await bot.send_message(admin_user.telegram_id, error_report)
                    except Exception as e:
                        print(f"Не удалось отправить отчет администратору {admin}: {e}")
        except:
            print(f"Критическая ошибка при создании VPN конфигураций: {e}")
    
    finally:
        await bot.session.close()

async def reassign_users_to_server(
    session: AsyncSession, 
    from_server_id: int, 
    to_server_id: int
) -> int:
    """
    Переназначить всех пользователей с одного сервера на другой
    с автоматическим созданием VPN конфигураций и уведомлениями
    """
    # Проверяем, что целевой сервер существует
    target_server = await get_server_by_id(session, to_server_id)
    if not target_server:
        raise ValueError(f"Сервер с ID {to_server_id} не найден")
    
    # Получаем информацию об исходном сервере
    source_server = await get_server_by_id(session, from_server_id)
    source_server_name = source_server.name if source_server else f"ID {from_server_id}"
    
    # Получаем всех пользователей с исходного сервера
    users_result = await session.execute(
        select(User).where(User.server_id == from_server_id)
    )
    users = users_result.scalars().all()
    
    if not users:
        return 0
    
    # Инициализируем бота для отправки уведомлений
    bot = Bot(token=BOT_TOKEN)
    
    current_time = datetime.utcnow()
    
    active_users_data = []  # Для фонового создания VPN конфигураций
    inactive_users_count = 0
    notified_users = 0
    
    try:
        for user in users:
            # Очищаем VPN конфигурацию
            user.vpn_link = None
            
            # Переназначаем на новый сервер
            user.server_id = to_server_id
            
            # Определяем тип пользователя и уведомления
            is_active = user.is_active and user.subscription_end and user.subscription_end > current_time
            
            if is_active:
                # Сохраняем данные для фонового создания VPN с продлением на 30 дней
                active_users_data.append({
                    'user_id': user.id,
                    'username': user.username,
                    'telegram_id': user.telegram_id,
                    'subscription_end': user.subscription_end,
                    'original_subscription_end': user.subscription_end  # Сохраняем исходную дату
                })
                
                # Отправляем предварительное уведомление
                try:
                    message = (
                        f"🔄 ПЕРЕНАЗНАЧЕНИЕ СЕРВЕРА\n\n"
                        f"Ваш сервер '{source_server_name}' временно недоступен. Мы переназначили вас на '{target_server.name}' и сейчас создаем новую VPN конфигурацию.\n\n"
                        f"⏳ Новая VPN ссылка будет отправлена в течение нескольких минут\n"
                        f"🎁 В качестве извинения мы продлим вашу подписку на 30 дней\n\n"
                        f"Спасибо за терпение! 🙏"
                    )
                    
                    await bot.send_message(user.telegram_id, message)
                    notified_users += 1
                except Exception as e:
                    print(f"Не удалось отправить предварительное уведомление пользователю {user.username}: {e}")
            else:
                # Для неактивных пользователей - только переназначаем, без компенсации
                inactive_users_count += 1
                
                try:
                    message = (
                        f"УВЕДОМЛЕНИЕ О ПЕРЕНАЗНАЧЕНИИ\n\n"
                        f"Ваш сервер '{source_server_name}' больше недоступен. Вы переназначены на '{target_server.name}'.\n\n"
                        f"Для возобновления VPN создайте новую конфигурацию в боте.\n\n"
                        f"Приносим извинения за неудобства! 🙏"
                    )
                    
                    await bot.send_message(user.telegram_id, message)
                    notified_users += 1
                except Exception as e:
                    print(f"Не удалось отправить уведомление неактивному пользователю {user.username}: {e}")
        
            # Сохраняем все изменения в базе данных
            await session.commit()
        
        # Отправляем промежуточный отчет администраторам
        admin_message = (
            f"📊 ОТЧЕТ О ПЕРЕНАЗНАЧЕНИИ ПОЛЬЗОВАТЕЛЕЙ\n\n"
            f"🔄 Переназначение с сервера '{source_server_name}' на '{target_server.name}'\n\n"
            f"📈 Статистика:\n"
            f"👥 Всего переназначено: {len(users)} пользователей\n"
            f"✅ Активных пользователей: {len(active_users_data)}\n"
            f"❌ Неактивных пользователей: {inactive_users_count}\n"
            f"📱 Успешно уведомлены: {notified_users}\n\n"
            f"🎁 Активным пользователям будет продлена подписка на 30 дней\n"
            f"🔄 Запущено фоновое создание VPN конфигураций для {len(active_users_data)} активных пользователей...\n\n"
            f"🕐 Время выполнения: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')} UTC"
        )
        
        try:
            for admin in ADMINS:
                if admin:
                    try:
                        result = await session.execute(
                            select(User).where(User.username == admin.replace('@', ''))
                        )
                        admin_user = result.scalar_one_or_none()
                        await bot.send_message(admin_user.telegram_id, admin_message)
                    except Exception as e:
                        print(f"Не удалось отправить отчет администратору {admin}: {e}")
        except Exception as e:
            print(f"Не удалось отправить отчет администраторам: {e}")
        
        # Запускаем фоновое создание VPN конфигураций для активных пользователей
        if active_users_data:
            await asyncio.create_task(_create_vpn_configs_in_background(
                active_users_data,
                to_server_id,
                source_server_name,
                target_server.name
            ))
        
        return len(users)
        
    except Exception as e:
        # В случае ошибки откатываем транзакцию
        await session.rollback()
        raise e
    finally:
        # Закрываем сессию бота
        await bot.session.close() 