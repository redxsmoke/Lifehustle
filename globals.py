import asyncpg

pool = None  # global placeholder

async def init_db_pool(dsn: str):
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn=dsn)
    return pool
