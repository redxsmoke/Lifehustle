# db_utils.py
import asyncpg

async def get_user(pool: asyncpg.pool.Pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT * FROM users WHERE user_id = $1
        ''', user_id)

async def get_eligible_occupations(pool: asyncpg.pool.Pool, user_education_level: int):
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT cd_occupation_id, description
            FROM cd_occupations
            WHERE active = TRUE AND education_level_id <= $1
            ORDER BY education_level_id, pay_rate DESC
        ''', user_education_level)

async def assign_user_job(pool: asyncpg.pool.Pool, user_id: int, occupation_id: int):
    async with pool.acquire() as conn:
        # Validate occupation exists and is active
        valid = await conn.fetchval('''
            SELECT EXISTS(
                SELECT 1 FROM cd_occupations
                WHERE cd_occupation_id = $1 AND active = TRUE
            )
        ''', occupation_id)
        if not valid:
            return False

        await conn.execute('''
            UPDATE users
            SET occupation_id = $1,
                job_start_date = NOW(),
                job_termination_date = NULL
            WHERE user_id = $2
        ''', occupation_id, user_id)

        return True
