from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from db.database import async_session
from db.models import User
from sqlalchemy import select, update, or_, and_
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram import types
from config.config import BOT_TOKEN, ADMIN_NAME_1, ADMIN_NAME_2
from db.service.user_cleanup_service import (
    cleanup_expired_users, get_cleanup_stats
)
import asyncio

bot = Bot(token=BOT_TOKEN)
scheduler = AsyncIOScheduler()
ADMINS = [ADMIN_NAME_1, ADMIN_NAME_2]

async def check_expired_subscriptions():
    """Проверяет истекшие подписки"""
    async with async_session() as session:
        now = datetime.utcnow()
        stmt = select(User).where(
            User.subscription_end < now,
            User.is_active == True
        )
        result = await session.execute(stmt)
        expired_users = result.scalars().all()
        
        # Отправляем уведомления и деактивируем подписки
        for user in expired_users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "⚠️ Ваша подписка истекла!\n\n",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
                                                            [
                                                                [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
                                                            ])
                )
            except Exception as e:
                print(f"Error sending message to user {user.telegram_id}: {e}")
            
            # Деактивируем подписку
            stmt = update(User).where(User.id == user.id).values(is_active=False)
            await session.execute(stmt)
            await session.commit()


async def check_upcoming_expirations():
    """Проверяет подписки, истекающие через 1 или 2 дня и уведомляет пользователей."""
    async with async_session() as session:
        now = datetime.utcnow()
        tomorrow_start = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        tomorrow_end = datetime.combine(now.date() + timedelta(days=1), datetime.max.time())

        day_after_start = datetime.combine(now.date() + timedelta(days=2), datetime.min.time())
        day_after_end = datetime.combine(now.date() + timedelta(days=2), datetime.max.time())

        result = await session.execute(select(User).where(
            User.is_active == True,
            or_(
                and_(
                    User.subscription_end >= tomorrow_start,
                    User.subscription_end <= tomorrow_end
                ),
                and_(
                    User.subscription_end >= day_after_start,
                    User.subscription_end <= day_after_end
                )
            )
        ))
        users = result.scalars().all()

        for user in users:
            end_date = user.subscription_end.date()
            if end_date == (now.date() + timedelta(days=1)):
                message = (
                    "⚠️ Ваша подписка истекает завтра!\n\n"
                )
            elif end_date == (now.date() + timedelta(days=2)):
                message = (
                    "⚠️ Ваша подписка истекает через 2 дня!\n\n"
                )
            try:
                await bot.send_message(user.telegram_id, message, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=
                                                            [
                                                                [types.InlineKeyboardButton(text="Продлить подписку", callback_data='update_sub')]
                                                            ]))
            except Exception as e:
                print(f"Error sending message to user {user.telegram_id}: {e}")

async def cleanup_vpn_servers():
    """Автоматическая очистка VPN серверов от неактивных пользователей"""
    print(f"🧹 Запуск автоматической очистки VPN серверов - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with async_session() as session:
        try:
            # Получаем статистику ДО очистки
            stats_before = await get_cleanup_stats(session)
            
            # Выполняем очистку
            cleanup_result = await cleanup_expired_users(session, dry_run=False)
            
            # Получаем статистику ПОСЛЕ очистки
            stats_after = await get_cleanup_stats(session)
            
            # Формируем отчет для админов
            report = f"🧹 <b>Отчет об автоматической очистке VPN серверов</b>\n"
            report += f"📅 Время: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            
            report += f"📊 Результаты очистки:\n"
            report += f"✅ Найдено для очистки: {cleanup_result['total_found']}\n"
            report += f"🗑️ Успешно очищено: {cleanup_result['cleaned']}\n"
            report += f"❌ Ошибок: {cleanup_result['errors']}\n\n"
            
            if cleanup_result['cleaned'] > 0:
                report += f"👥 <b>Очищенные пользователи:</b>\n"
                for user_info in cleanup_result['users'][:10]:  # Показываем первых 10
                    if user_info.get('status') == 'cleaned':
                        trial_mark = "🎯" if user_info['trial_used'] else "⭕"
                        server_display = user_info['server_id'] if user_info['server_id'] else 'Не назначен'
                        report += f"• @{user_info['username']} {trial_mark} (сервер {server_display})\n"
                        report += f"  Истекла {user_info['days_since_expired']} дн. назад\n"
                
                if cleanup_result['cleaned'] > 10:
                    report += f"... и еще {cleanup_result['cleaned'] - 10} пользователей\n"
                report += "\n"
            
            report += f"📈 <b>Статистика до/после очистки:</b>\n"
            report += f"👥 Всего пользователей: {stats_before['total_users']} → {stats_after['total_users']}\n"
            report += f"✅ Активных: {stats_before['active_users']} → {stats_after['active_users']}\n"
            report += f"🖥️ С VPN конфигами: {stats_before['users_with_vpn']} → {stats_after['users_with_vpn']}\n"
            report += f"🗑️ Кандидатов на очистку: {stats_before['cleanup_candidates']} → {stats_after['cleanup_candidates']}\n"
            
            if cleanup_result['errors'] > 0:
                report += f"\n⚠️ <b>Ошибки при очистке:</b> {cleanup_result['errors']}\n"
                report += f"Проверьте логи для деталей."
            
            # Отправляем отчет всем админам
            for admin in ADMINS:
                if admin:  # Проверяем, что админ указан
                    try:
                        # Пытаемся найти telegram_id админа
                        result = await session.execute(
                            select(User).where(User.username == admin.replace('@', ''))
                        )
                        admin_user = result.scalar_one_or_none()
                        
                        if admin_user:
                            await bot.send_message(
                                admin_user.telegram_id,
                                report,
                                parse_mode='HTML'
                            )
                            print(f"✅ Отчет отправлен админу @{admin}")
                        else:
                            print(f"⚠️ Админ @{admin} не найден в базе данных")
                            
                    except Exception as e:
                        print(f"❌ Ошибка отправки отчета админу @{admin}: {e}")
            
            print(f"✅ Автоматическая очистка завершена. Очищено: {cleanup_result['cleaned']}, ошибок: {cleanup_result['errors']}")
            
        except Exception as e:
            error_msg = f"❌ Ошибка при автоматической очистке VPN серверов: {e}"
            print(error_msg)
            
            # Уведомляем админов об ошибке
            for admin in ADMINS:
                if admin:
                    try:
                        result = await session.execute(
                            select(User).where(User.username == admin.replace('@', ''))
                        )
                        admin_user = result.scalar_one_or_none()
                        
                        if admin_user:
                            await bot.send_message(
                                admin_user.telegram_id,
                                f"🚨 **Ошибка автоматической очистки VPN**\n\n"
                                f"📅 Время: {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}\n"
                                f"❌ Ошибка: {str(e)}\n\n"
                                f"Требуется ручная проверка системы.",
                                parse_mode='Markdown'
                            )
                    except Exception as notify_error:
                        print(f"❌ Не удалось уведомить админа @{admin} об ошибке: {notify_error}")

def start_scheduler():
    """Запускает планировщик"""
    # Проверяем истекшие подписки каждый день в полночь
    scheduler.add_job(
        check_expired_subscriptions,
        CronTrigger(hour=9, minute=0),
        id='check_subscriptions',
        replace_existing=True
    )
    
    # Проверяем подписки, которые скоро истекают, каждый день в 12:00
    scheduler.add_job(
        check_upcoming_expirations,
        CronTrigger(hour=12, minute=0),
        id='check_upcoming_expirations',
        replace_existing=True
    )
    
    # Автоматическая очистка VPN серверов каждый день в 02:00
    scheduler.add_job(
        cleanup_vpn_servers,
        CronTrigger(hour=2, minute=0),
        id='cleanup_vpn_servers',
        replace_existing=True
    )
    
    scheduler.start() 