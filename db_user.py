import json
import asyncpg
import datetime

 

#------------ADD USER TO DB IF MISSING AND RUN COMMAND = TRUE--------------
async def ensure_user_exists(pool, user_id: int, user_name: str, guild_id: int | None):
    print(f"🔎 ensure_user_exists called for {user_name} ({user_id}) in guild {guild_id}")

    if guild_id is None:
        print(f"❌ Skipping user insert: guild_id is None for user {user_name}")
        return

    try:
        existing = await pool.fetchval("""
            SELECT 1 FROM users WHERE user_id = $1 AND guild_id = $2
        """, user_id, guild_id)

        print(f"Existing user check result: {existing}")

        if existing:
            print(f"ℹ️ User already exists in DB: {user_name} ({user_id}) in guild {guild_id}")
            return

        result = await pool.execute("""
            INSERT INTO users (
                user_id, user_name, guild_id, occupation_failed_days
            )
            VALUES ($1, $2, $3, 0)
            ON CONFLICT (user_id, guild_id) DO NOTHING
        """, user_id, user_name, guild_id)

        print(f"✅ DB Insert result: {result}")

        if result == "INSERT 0 0":
            print(f"⚠️ Insert skipped due to conflict (user likely exists): {user_name} ({user_id}) in guild {guild_id}")

    except Exception as e:
        print(f"❌ Exception during insert: {e}")


import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")  # Or hardcode your connection string here

async def add_unique_constraint():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            ALTER TABLE users
            ADD CONSTRAINT users_user_id_guild_id_unique UNIQUE (user_id, guild_id);
        """)
        print("✅ Unique constraint added on (user_id, guild_id).")
    except asyncpg.exceptions.DuplicateObjectError:
        print("⚠️ Unique constraint already exists.")
    except Exception as e:
        print(f"❌ Error adding unique constraint: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_unique_constraint())




# ---------- USERS TABLE (Profile Info) ----------
async def get_user(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        if row:
            return dict(row)  # <-- converts asyncpg Record to a full dictionary
        return None


async def upsert_user(pool, user_id: int, data: dict):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, user_name, last_seen, education_level_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                user_name = EXCLUDED.user_name,
                last_seen = EXCLUDED.last_seen
        ''', user_id,
             data.get('user_name'),
             data.get('last_seen'),
             1  # default education_level_id
        )


# ---------- USER_FINANCES TABLE (Money, Debts, Paycheck Timestamp) ----------
async def upsert_user_finances(pool, user_id: int, finances: dict):
    async with pool.acquire() as conn:
        # Ensure last_paycheck_claimed is always a timezone-aware datetime object
        last_claim = finances.get('last_paycheck_claimed')
        if last_claim is None:
            last_claim = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        elif isinstance(last_claim, (int, float)):
            last_claim = datetime.datetime.fromtimestamp(last_claim, tz=datetime.timezone.utc)
        elif not isinstance(last_claim, datetime.datetime):
            try:
                last_claim = datetime.datetime.fromisoformat(str(last_claim))
                if last_claim.tzinfo is None:
                    # Assume UTC if no timezone info present
                    last_claim = last_claim.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                last_claim = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)

        await conn.execute('''
            INSERT INTO user_finances (user_id, checking_account_balance, savings_account_balance, debt_balance, last_paycheck_claimed)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
                checking_account_balance = EXCLUDED.checking_account_balance,
                savings_account_balance = EXCLUDED.savings_account_balance,
                debt_balance = EXCLUDED.debt_balance,
                last_paycheck_claimed = EXCLUDED.last_paycheck_claimed
        ''', user_id,
             finances.get('checking_account_balance', 0),
             finances.get('savings_account_balance', 0),
             finances.get('debt_balance', 0),
             last_claim
        )


async def get_user_finances(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_finances WHERE user_id = $1",
            user_id
        )
        if row:
            return {
                'checking_account_balance': row['checking_account_balance'],
                'savings_account_balance': row['savings_account_balance'],
                'debt_balance': row['debt_balance'],
                'last_paycheck_claimed': row['last_paycheck_claimed']
            }
        return None


# ---------- USER_GROCERY_INVENTORY ----------
async def get_grocery_stash(pool, user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                cgc.name AS category,
                cgc.emoji AS category_emoji,
                cgt.name AS item_name,
                cgt.emoji AS item_emoji,
                ugi.quantity,
                ugi.expiration_date
            FROM user_grocery_inventory ugi 
            JOIN cd_grocery_type cgt ON cgt.id = ugi.grocery_type_id
            JOIN cd_grocery_category cgc ON cgc.id = ugi.grocery_category_id
            WHERE ugi.user_id = $1 AND ugi.sold_at IS NULL
            ORDER BY cgc.name, cgt.name;
        """, user_id)
    return rows

#-------------USER RESALE OF VEHICLE-------------
async def fetch_vehicle_with_pricing(pool, user_id, vehicle_id: int):
    sql = """
        SELECT uvi.*, cvt.cost AS base_price, uvi.resale_percent
        FROM user_vehicle_inventory uvi
        JOIN cd_vehicle_type cvt ON uvi.vehicle_type_id = cvt.id
        WHERE uvi.id = $1
    """
    record = await pool.fetchrow(sql, vehicle_id)
    return record

async def get_user_achievements(pool, user_id: int):
    query = """
    SELECT achievement_emoji, achievement_name, achievement_description
    FROM user_achievements
    WHERE user_id = $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, user_id)
    return rows

async def can_user_own_vehicle(user_id: int, vehicle_type_id: int, conn) -> bool:
    query = """
        SELECT vehicle_type_id, COUNT(*) as count
        FROM user_vehicle_inventory
        WHERE user_id = $1
        GROUP BY vehicle_type_id;
    """
    rows = await conn.fetch(query, user_id)
    counts = {row['vehicle_type_id']: row['count'] for row in rows}

    has_garage_row = await conn.fetchrow("SELECT has_garage FROM users WHERE user_id = $1", user_id)
    has_garage = has_garage_row['has_garage'] if has_garage_row else False

    CAR_TYPE_ID = 1  # replace with your actual ID
    BIKE_TYPE_ID = 2  # replace with your actual ID

    car_limit = 5 if has_garage else 1
    bike_limit = 1

    if vehicle_type_id == CAR_TYPE_ID:
        return counts.get(CAR_TYPE_ID, 0) < car_limit
    elif vehicle_type_id == BIKE_TYPE_ID:
        return counts.get(BIKE_TYPE_ID, 0) < bike_limit
    else:
        return False  # Unknown vehicle type
