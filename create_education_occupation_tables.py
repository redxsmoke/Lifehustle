import asyncio
import asyncpg

CREATE_CD_EDUCATION_LEVELS = """
CREATE TABLE IF NOT EXISTS cd_education_levels (
    cd_education_level_id SERIAL PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    level_order INTEGER,
    notes TEXT
);
"""

CREATE_CD_OCCUPATIONS = """
CREATE TABLE IF NOT EXISTS cd_occupations (
    cd_occupation_id SERIAL PRIMARY KEY,
    description VARCHAR(100) NOT NULL,
    pay_rate INTEGER NOT NULL,
    required_shifts_per_day INTEGER NOT NULL,
    education_level_id INTEGER REFERENCES cd_education_levels(cd_education_level_id),
    other_requirements VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
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

ALTER_USERS_TABLE = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS occupation_id INTEGER REFERENCES cd_occupations(cd_occupation_id),
    ADD COLUMN IF NOT EXISTS job_start_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS job_termination_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS education_level_id INTEGER REFERENCES cd_education_levels(cd_education_level_id);
"""

async def setup_db():
    conn = await asyncpg.connect(user='your_user', password='your_password', database='your_db', host='localhost')

    try:
        await conn.execute(CREATE_CD_EDUCATION_LEVELS)
        await conn.execute(CREATE_CD_OCCUPATIONS)
        await conn.execute(CREATE_CD_DESTINATIONS)
        await conn.execute(ALTER_USERS_TABLE)
        print("Tables created and users table altered successfully.")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(setup_db())
