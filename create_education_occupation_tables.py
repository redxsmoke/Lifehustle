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


EDUCATION_LEVELS = [
    (1, "None", 0, "No formal education"),
    (2, "High School Diploma", 1, "Basic education level"),
    (3, "Associate's Degree", 2, "Some college"),
    (4, "Bachelor's Degree", 3, "Undergraduate degree"),
    (5, "Master's Degree", 4, "Graduate degree"),
    (6, "PhD", 5, "Doctorate, highest academic level"),
]

 

async def seed_education_levels(conn):
    query = """
    INSERT INTO cd_education_levels (cd_education_level_id, description, level_order, notes)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (cd_education_level_id) DO NOTHING;
    """
    for level in EDUCATION_LEVELS:
        await conn.execute(query, *level)

async def seed_occupations(conn):
    query = """
    INSERT INTO cd_occupations
    (cd_occupation_id, company_name, description, pay_rate, required_shifts_per_day, education_level_id, other_requirements, active)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (cd_occupation_id) DO NOTHING;
    """
    for occ in OCCUPATIONS:
        await conn.execute(query, *occ)

async def setup():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        conn = await asyncpg.connect(dsn=db_url)
    else:
        conn = await asyncpg.connect(
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            database=os.getenv("PGDATABASE"),
            host=os.getenv("PGHOST"),
            port=int(os.getenv("PGPORT", 5432))
        )

    try:
        await conn.execute(CREATE_CD_EDUCATION_LEVELS)
        await conn.execute(CREATE_CD_OCCUPATIONS)
        await conn.execute(CREATE_CD_DESTINATIONS)
        await conn.execute(CREATE_USER_WORK_LOG)
        await conn.execute(ALTER_USERS_TABLE)
        await seed_education_levels(conn)
        await seed_occupations(conn)
        print("✅ Tables created and data seeded.")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(setup())
