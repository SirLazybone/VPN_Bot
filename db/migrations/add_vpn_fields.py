from sqlalchemy import text
from db.database import engine

async def run_migration():
    """
    Добавляет новые поля для VPN в таблицу users
    """
    async with engine.begin() as conn:
        # Добавляем новые колонки
        await conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP,
            ADD COLUMN IF NOT EXISTS vpn_link TEXT
        """))
        
        # Обновляем существующие записи
        await conn.execute(text("""
            UPDATE users 
            SET subscription_end = subscription_start + INTERVAL '30 days'
            WHERE subscription_start IS NOT NULL AND subscription_end IS NULL
        """))

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration()) 