import asyncio
import asyncpg
import os

CREATE_CD_EDUCATION_LEVELS = """
CREATE TABLE IF NOT EXISTS cd_education_levels (
    cd_education_level_id SERIAL PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    level_order INTEGER,
    notes TEXT
);
"""

DROP_CD_OCCUPATIONS = "DROP TABLE IF EXISTS cd_occupations CASCADE;"

CREATE_CD_OCCUPATIONS = """
CREATE TABLE IF NOT EXISTS cd_occupations (
    cd_occupation_id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    description VARCHAR(100) NOT NULL,
    pay_rate INTEGER NOT NULL,
    required_shifts_per_day INTEGER NOT NULL,
    education_level_id INTEGER NOT NULL,
    other_requirements TEXT,
    active BOOLEAN DEFAULT TRUE
);
"""

CREATE_CD_DESTINATIONS = """
CREATE TABLE IF NOT EXISTS cd_destinations (
    cd_destination_id SERIAL PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    destination_type VARCHAR(50),
    available BOOLEAN DEFAULT TRUE,
    travel_cost INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

CREATE_USER_WORK_LOG = """
CREATE TABLE IF NOT EXISTS user_work_log (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    work_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

ALTER_USERS_TABLE = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS occupation_id INTEGER REFERENCES cd_occupations(cd_occupation_id),
    ADD COLUMN IF NOT EXISTS job_start_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS job_termination_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS education_level_id INTEGER REFERENCES cd_education_levels(cd_education_level_id),
    ADD COLUMN IF NOT EXISTS guild_id BIGINT;
"""

DROP_GUILD_ID_DEFAULT = """
ALTER TABLE users ALTER COLUMN guild_id DROP DEFAULT;
"""

ALTER_USERS_COLUMN_TYPES = """
ALTER TABLE users
    ALTER COLUMN guild_id TYPE BIGINT USING guild_id::bigint,
    ALTER COLUMN user_id TYPE BIGINT USING user_id::bigint;
"""

async def alter_column_types(pool):
    async with pool.acquire() as conn:
        await conn.execute(DROP_GUILD_ID_DEFAULT)
        await conn.execute(ALTER_USERS_COLUMN_TYPES)
    print("✅ Column types altered successfully.")

async def setup():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        pool = await asyncpg.create_pool(dsn=db_url)
    else:
        pool = await asyncpg.create_pool(
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            database=os.getenv("PGDATABASE"),
            host=os.getenv("PGHOST"),
            port=int(os.getenv("PGPORT", 5432))
        )

    async with pool.acquire() as conn:
        await conn.execute(CREATE_CD_EDUCATION_LEVELS)
        await conn.execute(DROP_CD_OCCUPATIONS)
        await conn.execute(CREATE_CD_OCCUPATIONS)
        await conn.execute(CREATE_CD_DESTINATIONS)
        await conn.execute(CREATE_USER_WORK_LOG)
        await conn.execute(ALTER_USERS_TABLE)

    await alter_column_types(pool)
    await pool.close()
    print("✅ Tables created and columns altered.")

if __name__ == '__main__':
    asyncio.run(setup())
