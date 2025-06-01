from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db.models import User, Server
from typing import List, Optional
from datetime import datetime, timedelta
from bot.vpn_manager import VPNManager

async def get_users_for_cleanup(session: AsyncSession) -> List[User]:
    """
    Получить пользователей для очистки с VPN серверов:
    - is_active = False И прошла неделя с subscription_end
    """
    one_week_ago = datetime.utcnow() - timedelta(weeks=1)
    
    result = await session.execute(
        select(User).where(
            User.is_active == False,
            User.subscription_end.isnot(None),
            User.subscription_end < one_week_ago,
            User.vpn_link.isnot(None)  # Только те, у кого есть VPN конфиг
        ).order_by(User.subscription_end)
    )
    return result.scalars().all()

async def get_users_without_trial(session: AsyncSession) -> List[User]:
    """Получить пользователей, которые не использовали пробный период"""
    result = await session.execute(
        select(User).where(
            User.trial_used == False,
            User.vpn_link.is_(None)
        )
    )
    return result.scalars().all()

async def cleanup_user_from_server(
    session: AsyncSession, 
    user: User,
    reason: str = "cleanup"
) -> bool:
    """
    Удаляет пользователя с VPN сервера, но оставляет в боте
    """
    try:
        vpn_manager = VPNManager(session)
        success = await vpn_manager.delete_user(user.username, server_id=user.server_id)
        
        if success:
            # Обновляем состояние пользователя в БД
            user.vpn_link = None  # Удаляем VPN ссылку
            user.is_active = False
            user.server_id = None
            # server_id оставляем для истории, на каком сервере был пользователь
            # is_active и trial_used не трогаем для сохранения истории
            
            await session.commit()
            print(f"✅ Пользователь {user.username} удален с сервера {user.server_id} ({reason})")
            return True
        else:
            print(f"❌ Не удалось удалить пользователя {user.username} с сервера {user.server_id}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при удалении пользователя {user.username}: {e}")
        return False

async def cleanup_expired_users(
    session: AsyncSession,
    dry_run: bool = True
) -> dict:
    """
    Очищает пользователей с истекшей подпиской (неактивных более недели)
    """
    users_for_cleanup = await get_users_for_cleanup(session)
    
    result = {
        "total_found": len(users_for_cleanup),
        "cleaned": 0,
        "errors": 0,
        "users": []
    }
    
    for user in users_for_cleanup:
        # Вычисляем сколько дней прошло с окончания подписки
        days_since_expired = (datetime.utcnow() - user.subscription_end).days
        
        user_info = {
            "username": user.username,
            "server_id": user.server_id,
            "subscription_end": user.subscription_end,
            "days_since_expired": days_since_expired,
            "trial_used": user.trial_used
        }
        
        if not dry_run:
            success = await cleanup_user_from_server(
                session, user, 
                reason=f"expired_{days_since_expired}d_ago"
            )
            if success:
                result["cleaned"] += 1
                user_info["status"] = "cleaned"
            else:
                result["errors"] += 1
                user_info["status"] = "error"
        else:
            user_info["status"] = "would_clean"
        
        result["users"].append(user_info)
    
    return result

async def mark_trial_as_used(session: AsyncSession, user: User):
    """Помечает пробный период как использованный"""
    user.trial_used = True
    await session.commit()

async def get_cleanup_stats(session: AsyncSession) -> dict:
    """Получить статистику для очистки"""
    stats = {}
    
    # Всего пользователей
    total_result = await session.execute(select(User))
    stats["total_users"] = len(total_result.scalars().all())
    
    # Активных пользователей (с активной подпиской)
    active_result = await session.execute(
        select(User).where(User.is_active == True)
    )
    stats["active_users"] = len(active_result.scalars().all())
    
    # Пользователей с VPN конфигами
    with_vpn_result = await session.execute(
        select(User).where(User.vpn_link.isnot(None))
    )
    stats["users_with_vpn"] = len(with_vpn_result.scalars().all())
    
    # Использовали пробный период
    trial_result = await session.execute(
        select(User).where(User.trial_used == True)
    )
    stats["trial_used_count"] = len(trial_result.scalars().all())
    
    # Кандидаты на очистку (неактивные более недели)
    cleanup_candidates = await get_users_for_cleanup(session)
    stats["cleanup_candidates"] = len(cleanup_candidates)
    
    return stats

async def get_server_cleanup_stats(session: AsyncSession, server_id: int) -> dict:
    """Получить статистику очистки для конкретного сервера"""
    stats = {}
    
    # Всего пользователей на сервере
    total_result = await session.execute(
        select(User).where(User.server_id == server_id)
    )
    stats["total_users"] = len(total_result.scalars().all())
    
    # Активных на сервере
    active_result = await session.execute(
        select(User).where(
            User.server_id == server_id,
            User.is_active == True
        )
    )
    stats["active_users"] = len(active_result.scalars().all())
    
    # С VPN конфигами на сервере
    with_vpn_result = await session.execute(
        select(User).where(
            User.server_id == server_id,
            User.vpn_link.isnot(None)
        )
    )
    stats["users_with_vpn"] = len(with_vpn_result.scalars().all())
    
    # Кандидаты на очистку на этом сервере
    cleanup_result = await session.execute(
        select(User).where(
            User.server_id == server_id,
            User.is_active == False,
            User.subscription_end.isnot(None),
            User.subscription_end < datetime.utcnow() - timedelta(weeks=1),
            User.vpn_link.isnot(None)
        )
    )
    stats["cleanup_candidates"] = len(cleanup_result.scalars().all())
    
    return stats 