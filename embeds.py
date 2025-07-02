import discord

def embed_message(title: str, description: str, color: discord.Color = discord.Color.default()) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    return embed
