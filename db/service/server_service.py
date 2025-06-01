from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from db.models import Server, User
from typing import List, Optional

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
    server = result.scalar_one_or_none()
    
    # Если нет сервера по умолчанию, возвращаем первый активный
    if not server:
        result = await session.execute(
            select(Server).where(Server.is_active == True).order_by(Server.id).limit(1)
        )
        server = result.scalar_one_or_none()
    
    return server

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

async def reassign_users_to_server(
    session: AsyncSession, 
    from_server_id: int, 
    to_server_id: int
) -> int:
    """Переназначить всех пользователей с одного сервера на другой"""
    # Проверяем, что целевой сервер существует
    target_server = await get_server_by_id(session, to_server_id)
    if not target_server:
        raise ValueError(f"Сервер с ID {to_server_id} не найден")
    
    # Переназначаем пользователей
    result = await session.execute(
        update(User)
        .where(User.server_id == from_server_id)
        .values(server_id=to_server_id)
    )
    
    await session.commit()
    return result.rowcount 