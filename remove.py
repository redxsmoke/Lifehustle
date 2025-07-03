async def remove_vehicle_by_id(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM cd_vehicle_type
            WHERE id IN (151, 152)
        """)
        print("✅ Successfully deleted vehicles with IDs 151 and 152.")
