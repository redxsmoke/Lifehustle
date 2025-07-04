import asyncio
import asyncpg
import os

async def drop_and_recreate_user_vehicle_inventory():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise EnvironmentError("DATABASE_URL env var not found")

    pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    drop_query = "DROP TABLE IF EXISTS user_vehicle_inventory CASCADE;"
    create_query = """
    CREATE TABLE user_vehicle_inventory (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        vehicle_type_id INTEGER NOT NULL,
        color VARCHAR(50),
        appearance_description TEXT,
        plate_number VARCHAR(20),
        condition_id INTEGER,
        condition VARCHAR(50),
        commute_count INTEGER DEFAULT 0,
        resale_value NUMERIC DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        sold_at TIMESTAMPTZ,
        resale_percent NUMERIC DEFAULT 0
    );
    """

    async with pool.acquire() as conn:
        await conn.execute(drop_query)
        await conn.execute(create_query)
    print("Dropped and recreated user_vehicle_inventory with condition_id column.")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(drop_and_recreate_user_vehicle_inventory())
