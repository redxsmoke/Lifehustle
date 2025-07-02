import json
from discord import app_commands

# Load categories data on import so it's available globally
def load_categories():
    with open("categories.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data  # Or data.get("Foods", {})

# Load shop items (optional here, but useful)
def load_shop_items():
    with open("shop_items.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

# Load once at import time
categories = load_categories()

# Autocomplete function for category names
async def category_autocomplete(interaction: app_commands.Interaction, current: str):
    results = [
        app_commands.Choice(name=cat, value=cat)
        for cat in categories.keys()
        if current.lower() in cat.lower()
    ]
    return results[:25]  # Discord allows max 25 choices
