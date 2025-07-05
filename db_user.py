import json
import asyncpg
import datetime


# ---------- USERS TABLE (Profile Info) ----------

async def get_user(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
        if row:
            return {
                'user_id': row['user_id'],
                'user_name': row['user_name'],
                'last_seen': row['last_seen']
            }
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
