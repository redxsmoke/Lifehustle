import discord

def embed_message(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=title, description=description)
    return embed
