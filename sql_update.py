import os
import asyncio
import asyncpg

async def update_vehicle_types():
    database_url = os.getenv("DATABASE_URL")  # Railway usually sets this env var
    if not database_url:
        print("DATABASE_URL environment variable not found.")
        return

    conn = await asyncpg.connect(database_url)
    try:
        # Remove Blue Car and Red Car
        await conn.execute("""
            DELETE FROM cd_vehicle_type WHERE name IN ('Blue Car', 'Red Car');
        """)
        print("Removed Blue Car and Red Car")

        # Insert Motorcycle
        await conn.execute("""
            INSERT INTO cd_vehicle_type (name, emoji, cost, condition, resale_value_range)
            VALUES ('Motorcycle', '🏍️', 8000, 'new', '4000-6000');
        """)
        print("Added Motorcycle")
    finally:
        await conn.close()

asyncio.run(update_vehicle_types())
