import json
from discord import Interaction
from discord import app_commands

def load_categories():
    with open("categories.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

categories = load_categories()

async def category_autocomplete(interaction: Interaction, current: str):
    results = [
        app_commands.Choice(name=cat, value=cat)
        for cat in categories.keys()
        if current.lower() in cat.lower()
    ]
    return results[:25]
