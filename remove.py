import asyncio
from globals import pool  # Assumes your pool is defined and initialized here

async def delete_red_and_blue_cars():
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM cd_vehicle_type
            WHERE name IN ('Red Car', 'Blue Car');
        """)
        print("✅ Red Car and Blue Car deleted from cd_vehicle_type")

# Optional: to run immediately when script is executed
if __name__ == "__main__":
    asyncio.run(delete_red_and_blue_cars())
