import asyncio
import asyncpg
import os

async def reset_user_secret_button_table():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set!")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("DROP TABLE IF EXISTS user_achievements;")
        await conn.execute("""
            CREATE TABLE user_achievements (
                user_id BIGINT PRIMARY KEY,
                achievement_id BIG INT NULL,
                achievement_name TEXT NULL,
                achievement_description TEXT NULL,
                achievement_emoji TEXT NULL,
                date_unlocked DATE NULL,
                guild_id BIGINT NOT NULL                
            );
        """)
        print("✅ user_achievements table reset successfully.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(reset_user_secret_button_table())
