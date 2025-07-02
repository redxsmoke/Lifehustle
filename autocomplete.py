import discord
from discord import app_commands
from category_loader import load_categories

categories = load_categories()

async def category_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    choices = []
    current_lower = current.lower()

    for category in categories.keys():
        if category.lower().startswith(current_lower):
            choices.append(app_commands.Choice(name=category, value=category))
        if len(choices) >= 25:
            break

    return choices

async def commute_method_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    methods = ["drive", "bike", "subway", "bus"]
    current_lower = current.lower()

    choices = [
        app_commands.Choice(name=method, value=method)
        for method in methods
        if method.startswith(current_lower)
    ]
    return choices

async def commute_direction_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    directions = ["north", "south", "east", "west"]
    current_lower = current.lower()

    choices = [
        app_commands.Choice(name=direction, value=direction)
        for direction in directions
        if direction.startswith(current_lower)
    ]
    return choices
