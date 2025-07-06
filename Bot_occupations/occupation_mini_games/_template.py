import discord

async def play(pool, guild_id, user_id, user_occupation_id):
    """
    Mini-game logic triggered during a workshift.

    Returns a dict with:
    - title: Title of the minigame (string)
    - description: Result text to show the user (string)
    - bonus: Optional int payout (0 if none)
    """

    # Example: Fetch the user's job name
    async with pool.acquire() as conn:
        user_job = await conn.fetchval("""
            SELECT name FROM cd_occupation WHERE id = $1
        """, user_occupation_id)

    # === Replace this with your custom game logic ===
    title = "🚧 Example Mini-Game"
    description = f"You encountered something strange during your shift as a {user_job}!"
    bonus = 10  # or 0 if no bonus

    return {
        "title": title,
        "description": description,
        "bonus": bonus
    }
