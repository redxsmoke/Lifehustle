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
            INSERT INTO users (user_id, user_name, last_seen)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET
                user_name = EXCLUDED.user_name,
                last_seen = EXCLUDED.last_seen
        ''', user_id,
             data.get('user_name'),
             data.get('last_seen')
        )


# ---------- USER_FINANCES TABLE (Money, Debts, Paycheck Timestamp) ----------

async def get_user_finances(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM user_finances WHERE user_id = $1', user_id)
        if row:
            data = dict(row)
            # Normalize last_paycheck_claimed to a datetime (or epoch)
            if data.get('last_paycheck_claimed') is None:
                data['last_paycheck_claimed'] = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
            elif not isinstance(data['last_paycheck_claimed'], datetime.datetime):
                try:
                    data['last_paycheck_claimed'] = datetime.datetime.fromisoformat(str(data['last_paycheck_claimed']))
                except Exception:
                    data['last_paycheck_claimed'] = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
            return data
        return None


async def upsert_user_finances(pool, user_id: int, finances: dict):
    async with pool.acquire() as conn:
        # Ensure last_paycheck_claimed is always a datetime object
        last_claim = finances.get('last_paycheck_claimed')
        if last_claim is None:
            last_claim = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        elif isinstance(last_claim, (int, float)):
            last_claim = datetime.datetime.fromtimestamp(last_claim, tz=datetime.timezone.utc)
        elif not isinstance(last_claim, datetime.datetime):
            try:
                last_claim = datetime.datetime.fromisoformat(str(last_claim))
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
