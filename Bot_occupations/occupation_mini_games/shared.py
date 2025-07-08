import discord

def build_paystub_embed(paystub_data, mini_game_outcome=None, mini_game_outcome_type=None):
    description = (
        f"> You completed your shift as a **{paystub_data['occupation_name']}**.\n"
        f"> Base pay: **${paystub_data['pay_rate']:.2f}**\n"
    )
    if mini_game_outcome:
        description += f"\n**Mini-game outcome:**\n{mini_game_outcome}\n"

    embed = discord.Embed(
        title=f"🕒 Shift Logged - Pay Stub from ***{paystub_data['company_name']}***",
        description=description,
        color=discord.Color.green() if mini_game_outcome_type == "positive"
        else discord.Color.red() if mini_game_outcome_type == "negative"
        else discord.Color.gold()
    )
    return embed
