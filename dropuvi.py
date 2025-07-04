import asyncio
import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

DROP_TABLE_SQL = """
DROP TABLE IF EXISTS user_vehicle_inventory CASCADE;
"""

CREATE_TABLE_SQL = """
CREATE TABLE user_vehicle_inventory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    vehicle_type_id INT NOT NULL,
    color VARCHAR(50),
    appearance_description TEXT,
    plate_number VARCHAR(20),
    condition_id INT,
    condition VARCHAR(50),
    travel_count INT DEFAULT 0,
    resale_value NUMERIC(12, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sold_at TIMESTAMPTZ,
    resale_percent NUMERIC(5, 2)
);
"""

async def drop_and_recreate_uvi():
    if not DATABASE_URL:
        print("❌ DATABASE_URL environment variable not set.")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Dropping table if exists...")
        await conn.execute(DROP_TABLE_SQL)
        print("Creating table user_vehicle_inventory...")
        await conn.execute(CREATE_TABLE_SQL)
        print("✅ Table recreated successfully.")
    finally:
        await conn.close()

# Optional: Allow running this script directly for testing:
if __name__ == "__main__":
    asyncio.run(drop_and_recreate_uvi())
