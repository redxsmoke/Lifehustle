# Globals
import asyncpg
pool = None


async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(your_db_connection_string)