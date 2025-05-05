import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy import text
from database import engine
from models import Base

async def recreate_tables():
    async with engine.begin() as conn:
        # Drop existing tables if they exist
        await conn.execute(text("DROP TABLE IF EXISTS payments"))
        await conn.execute(text("DROP TABLE IF EXISTS users"))
        
        # Create new tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("Tables have been recreated successfully!")

if __name__ == "__main__":
    asyncio.run(recreate_tables()) 