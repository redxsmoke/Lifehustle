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

import asyncio
import asyncpg

EDUCATION_LEVELS = [
    (1, "None", 0, "No formal education"),
    (2, "High School Diploma", 1, "Basic education level"),
    (3, "Associate's Degree", 2, "Some college"),
    (4, "Bachelor's Degree", 3, "Undergraduate degree"),
    (5, "Master's Degree", 4, "Graduate degree"),
    (6, "PhD", 5, "Doctorate, highest academic level"),
]

OCCUPATIONS = [
    (1, "Professional Cuddler", 40, 1, "Must love hugs", True),
    (2, "Senior Bubble Wrap Popper", 35, 1, "PhD in stress relief", True),
    (3, "Street Performer", 30, 1, "Charismatic personality", True),
    (4, "Dog Walker", 45, 1, "Love for animals", True),
    (5, "Human Statue", 50, 1, "Ability to stand still for hours", True),
    (6, "Professional Line Sitter", 30, 1, "Patience and perseverance", True),
    (7, "Freelance Meme Curator", 45, 1, "Social media savvy", True),
    (8, "Test Subject", 50, 1, "Willingness to participate", True),
    (9, "Coffee Taster", 55, 1, "Highly sensitive palate", True),
    (10, "Parking Enforcement Officer", 60, 1, "Attention to detail", True),
    (11, "Grocery Store Clerk", 50, 2, None, True),
    (12, "Delivery Driver", 70, 2, "Driver’s license", True),
    (13, "Professional Mourner", 70, 2, "Empathy and acting skills", True),
    (14, "Pet Food Taster", 60, 2, "Strong stomach required", True),
    (15, "Professional Whistler", 80, 2, "Exceptional whistling talent", True),
    (16, "Ice Cream Truck Driver", 65, 2, "Driving license", True),
    (17, "Event Setup Crew", 55, 2, "Physical fitness", True),
    (18, "Janitor", 50, 2, "Reliability", True),
    (19, "Waiter/Waitress", 60, 2, "Good communication skills", True),
    (20, "Amusement Park Ride Operator", 65, 2, "Safety conscious", True),
    (21, "Office Assistant", 100, 3, "Basic computer skills", True),
    (22, "Ice Cream Flavor Developer", 90, 3, "Creative palate", True),
    (23, "Waterslide Tester", 120, 3, "Thrill-seeking", True),
    (24, "Odor Judge", 100, 3, "Nose for smells", True),
    (25, "Social Media Manager", 110, 3, "Social media savvy", True),
    (26, "Medical Assistant", 130, 3, "Medical knowledge", True),
    (27, "Graphic Designer", 125, 3, "Creativity", True),
    (28, "Lab Technician", 115, 3, "Detail-oriented", True),
    (29, "Event Coordinator", 120, 3, "Organization skills", True),
    (30, "Legal Assistant", 110, 3, "Knowledge of legal procedures", True),
    (31, "Software Developer", 200, 4, "Programming skills", True),
    (32, "VR World Architect", 150, 4, "Creativity + coding skills", True),
    (33, "Accountant", 180, 4, "Finance knowledge", True),
    (34, "Market Research Analyst", 170, 4, "Analytical skills", True),
    (35, "Engineer", 190, 4, "Engineering degree", True),
    (36, "Teacher", 160, 4, "Teaching skills", True),
    (37, "Journalist", 150, 4, "Strong writing skills", True),
    (38, "Architect", 190, 4, "Design skills", True),
    (39, "IT Consultant", 180, 4, "Technical knowledge", True),
    (40, "Business Analyst", 170, 4, "Analytical skills", True),
    (41, "Research Scientist", 250, 5, "Scientific knowledge", True),
    (42, "University Lecturer", 220, 5, "Teaching and research skills", True),
    (43, "Data Scientist", 240, 5, "Advanced data analysis", True),
    (44, "Clinical Psychologist", 230, 5, "Psychological knowledge", True),
    (45, "Environmental Consultant", 210, 5, "Environmental expertise", True),
    (46, "Pharmacist", 260, 5, "Medical knowledge", True),
    (47, "Urban Planner", 220, 5, "Planning skills", True),
    (48, "Economist", 230, 5, "Economic expertise", True),
    (49, "Statistician", 240, 5, "Statistical analysis", True),
    (50, "Policy Analyst", 210, 5, "Policy knowledge", True),
    (51, "Medical Doctor", 300, 6, "Medical license", True),
    (52, "University Professor", 220, 6, "Teaching skills", True),
    (53, "Head Honcho of Unicorn Wrangling", 250, 6, "Mythical creature expertise", True),
    (54, "Time-Traveling Tax Auditor", 300, 6, "Paradox-proof accounting", True),
    (55, "Chief Scientist", 280, 6, "Leadership and science", True),
    (56, "Aerospace Engineer", 290, 6, "Aeronautics expertise", True),
    (57, "Philosopher", 210, 6, "Deep thinking", True),
    (58, "Geneticist", 270, 6, "Genetic research", True),
    (59, "Quantum Physicist", 300, 6, "Quantum mechanics expertise", True),
    (60, "Galactic Ambassador", 300, 6, "Diplomacy and charm", True),
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
    INSERT INTO cd_occupations (cd_occupation_id, description, pay_rate, required_shifts_per_day, education_level_id, other_requirements, active)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (cd_occupation_id) DO NOTHING;
    """
    for occ in OCCUPATIONS:
        await conn.execute(query, *occ)

async def main():
    conn = await asyncpg.connect(user='your_user', password='your_password', database='your_db', host='localhost')
    try:
        await seed_education_levels(conn)
        await seed_occupations(conn)
        print("Seed data inserted successfully.")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())


async def create_user_work_log_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_work_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                work_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        print("✅ Created table: user_work_log")

async def setup_db():
    pool = await asyncpg.create_pool(
        user='your_user',
        password='your_password',
        database='your_database',
        host='localhost',  # or Railway DB host
        port=5432
    )
    await create_user_work_log_table(pool)
    await pool.close()

if __name__ == "__main__":
    asyncio.run(setup_db())