import discord
COLOR_RED = discord.Color.red()

def embed_message(title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = discord.utils.utcnow()
    return embed
