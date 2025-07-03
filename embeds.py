import discord

def embed_message(title, description, color):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = discord.utils.utcnow()
    return embed
