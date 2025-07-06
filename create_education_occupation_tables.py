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
    ADD COLUMN IF NOT EXISTS guild_id BIGINT;  -- make sure guild_id exists and is BIGINT
"""

ALTER_USERS_COLUMN_TYPES = """
ALTER TABLE users
    ALTER COLUMN guild_id TYPE BIGINT USING guild_id::bigint,
    ALTER COLUMN user_id TYPE BIGINT USING user_id::bigint;
"""

EDUCATION_LEVELS = [
    (1, "None", 0, "No formal education"),
    (2, "High School Diploma", 1, "Basic education level"),
    (3, "Associate's Degree", 2, "Some college"),
    (4, "Bachelor's Degree", 3, "Undergraduate degree"),
    (5, "Master's Degree", 4, "Graduate degree"),
    (6, "PhD", 5, "Doctorate, highest academic level"),
]

OCCUPATIONS = [
    (1, 'SnuggleWorks Inc.', 'Professional Cuddler', 40, 1, 1, 'Must love hugs', True),
    (2, 'BubblePop Labs', 'Senior Bubble Wrap Popper', 35, 1, 6, 'PhD in stress relief', True),
    (3, 'StreetStars Co.', 'Street Performer', 30, 1, 1, 'Charismatic personality', True),
    (4, 'Paws & Claws LLC', 'Dog Walker', 45, 1, 1, 'Love for animals', True),
    (5, 'Still Statues Ltd.', 'Human Statue', 50, 1, 1, 'Ability to stand still for hours', True),
    (6, 'LineBusters', 'Professional Line Sitter', 30, 1, 1, 'Patience and perseverance', True),
    (7, 'MemeStream', 'Freelance Meme Curator', 45, 1, 2, 'Social media savvy', True),
    (8, 'TestTube Inc.', 'Test Subject', 50, 1, 2, 'Willingness to participate', True),
    (9, 'Bean Brewmasters', 'Coffee Taster', 55, 1, 2, 'Highly sensitive palate', True),
    (10, 'ParkPatrol', 'Parking Enforcement Officer', 60, 1, 2, 'Attention to detail', True),
    (11, 'FreshMart', 'Grocery Store Clerk', 50, 2, 2, None, True),
    (12, 'DashDrivers', 'Delivery Driver', 70, 2, 2, 'Driver’s license', True),
    (13, 'Tears & Cheers', 'Professional Mourner', 70, 2, 2, 'Empathy and acting skills', True),
    (14, 'PawsTasters', 'Pet Food Taster', 60, 2, 2, 'Strong stomach required', True),
    (15, 'WhistleWorks', 'Professional Whistler', 80, 2, 2, 'Exceptional whistling talent', True),
    (16, 'Cool Scoops Inc.', 'Ice Cream Truck Driver', 65, 2, 2, 'Driving license', True),
    (17, 'Setup Squad', 'Event Setup Crew', 55, 2, 2, 'Physical fitness', True),
    (18, 'Clean Team', 'Janitor', 50, 2, 2, 'Reliability', True),
    (19, 'Service Pros', 'Waiter/Waitress', 60, 2, 2, 'Good communication skills', True),
    (20, 'ThrillRides Co.', 'Amusement Park Ride Operator', 65, 2, 2, 'Safety conscious', True),
    (21, 'Office Heroes', 'Office Assistant', 100, 3, 3, 'Basic computer skills', True),
    (22, 'Flavor Factory', 'Ice Cream Flavor Developer', 90, 3, 3, 'Creative palate', True),
    (23, 'Slide Testers', 'Waterslide Tester', 120, 3, 3, 'Thrill-seeking', True),
    (24, 'SniffRight', 'Odor Judge', 100, 3, 3, 'Nose for smells', True),
    (25, 'Buzz Media', 'Social Media Manager', 110, 3, 3, 'Social media savvy', True),
    (26, 'MediAssist', 'Medical Assistant', 130, 3, 3, 'Medical knowledge', True),
    (27, 'Creative Pixels', 'Graphic Designer', 125, 3, 3, 'Creativity', True),
    (28, 'LabWorks', 'Lab Technician', 115, 3, 3, 'Detail-oriented', True),
    (29, 'Event Masters', 'Event Coordinator', 120, 3, 3, 'Organization skills', True),
    (30, 'Law Partners', 'Legal Assistant', 110, 3, 3, 'Knowledge of legal procedures', True),
    (31, 'CodeSmiths', 'Software Developer', 200, 4, 4, 'Programming skills', True),
    (32, 'VR Builders', 'VR World Architect', 150, 4, 4, 'Creativity + coding skills', True),
    (33, 'Number Crunchers', 'Accountant', 180, 4, 4, 'Finance knowledge', True),
    (34, 'Market Insight', 'Market Research Analyst', 170, 4, 4, 'Analytical skills', True),
    (35, 'BuildTech', 'Engineer', 190, 4, 4, 'Engineering degree', True),
    (36, 'TeachWell', 'Teacher', 160, 4, 4, 'Teaching skills', True),
    (37, 'NewsFlash', 'Journalist', 150, 4, 4, 'Strong writing skills', True),
    (38, 'Design Pros', 'Architect', 190, 4, 4, 'Design skills', True),
    (39, 'Tech Advisors', 'IT Consultant', 180, 4, 4, 'Technical knowledge', True),
    (40, 'Biz Analysts', 'Business Analyst', 170, 4, 4, 'Analytical skills', True),
    (41, 'Science Hub', 'Research Scientist', 250, 5, 5, 'Scientific knowledge', True),
    (42, 'Uni Scholars', 'University Lecturer', 220, 5, 5, 'Teaching and research skills', True),
    (43, 'Data Wizards', 'Data Scientist', 240, 5, 5, 'Advanced data analysis', True),
    (44, 'MindCare', 'Clinical Psychologist', 230, 5, 5, 'Psychological knowledge', True),
    (45, 'EcoConsult', 'Environmental Consultant', 210, 5, 5, 'Environmental expertise', True),
    (46, 'PharmaLife', 'Pharmacist', 260, 5, 5, 'Medical knowledge', True),
    (47, 'City Planners', 'Urban Planner', 220, 5, 5, 'Planning skills', True),
    (48, 'Econ Experts', 'Economist', 230, 5, 5, 'Economic expertise', True),
    (49, 'StatsLab', 'Statistician', 240, 5, 5, 'Statistical analysis', True),
    (50, 'PolicyWorks', 'Policy Analyst', 210, 5, 5, 'Policy knowledge', True),
    (51, 'MedDoc Group', 'Medical Doctor', 300, 6, 6, 'Medical license', True),
    (52, 'Professors United', 'University Professor', 220, 6, 6, 'Teaching skills', True),
    (53, 'Unicorn Wranglers', 'Head Honcho of Unicorn Wrangling', 250, 6, 6, 'Mythical creature expertise', True),
    (54, 'Time Auditors Inc.', 'Time-Traveling Tax Auditor', 300, 6, 6, 'Paradox-proof accounting', True),
    (55, 'Chief Labs', 'Chief Scientist', 280, 6, 6, 'Leadership and science', True),
    (56, 'Aero Dynamics', 'Aerospace Engineer', 290, 6, 6, 'Aeronautics expertise', True),
    (57, 'Thinkers Club', 'Philosopher', 210, 6, 6, 'Deep thinking', True),
    (58, 'GeneWorks', 'Geneticist', 270, 6, 6, 'Genetic research', True),
    (59, 'Quantum Labs', 'Quantum Physicist', 300, 6, 6, 'Quantum mechanics expertise', True),
    (60, 'Galactic Embassy', 'Galactic Ambassador', 300, 6, 6, 'Diplomacy and charm', True),
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

async def alter_column_types(pool):
    async with pool.acquire() as conn:
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
        await seed_education_levels(conn)
        await seed_occupations(conn)

    await alter_column_types(pool)
    await pool.close()
    print("✅ Tables created, data seeded, and columns altered.")

if __name__ == '__main__':
    asyncio.run(setup())
