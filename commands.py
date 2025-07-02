# commands.py
import discord
from discord import app_commands, Interaction

def register_commands(tree: app_commands.CommandTree):
    print("→ register_commands() called")

    @tree.command(name="ping", description="Ping test command")
    async def ping(interaction: Interaction):
        print("→ /ping invoked")
        await interaction.response.send_message("Pong!")

    print("→ /ping registered")
