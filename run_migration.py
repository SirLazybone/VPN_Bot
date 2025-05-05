import asyncio
from db.migrations.add_vpn_fields import run_migration

if __name__ == "__main__":
    print("Running database migration...")
    asyncio.run(run_migration())
    print("Migration completed successfully!") 