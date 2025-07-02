import discord
from discord import app_commands, Interaction

def register_commands(tree: app_commands.CommandTree):
    @tree.command(name="ping", description="Ping test command")
    async def ping(interaction: Interaction):
        await interaction.response.send_message("Pong!")