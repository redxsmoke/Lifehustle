import asyncio
from globals import pool  # This assumes your pool is initialized before calling

async def remove_vehicle_by_id(vehicle_names: list[str]):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM cd_vehicle_type
            WHERE name = ANY($1)
        """, vehicle_names)
        print(f"✅ Removed vehicles: {', '.join(vehicle_names)}")

# Optional: Run directly
if __name__ == "__main__":
    asyncio.run(remove_vehicle_by_id(["Red Car", "Blue Car"]))
