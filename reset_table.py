import asyncio
import asyncpg
import os

async def reset_user_secret_button_table():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set!")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("DROP TABLE IF EXISTS user_secret_button;")
        await conn.execute("""
            CREATE TABLE user_secret_button (
                user_id BIGINT PRIMARY KEY,
                times_pressed INT NOT NULL DEFAULT 0,
                last_used TIMESTAMP
            );
        """)
        print("✅ user_secret_button table reset successfully.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(reset_user_secret_button_table())
