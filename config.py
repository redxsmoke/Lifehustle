import os
import sys

def get_env_int(key, default=None):
    try:
        value = os.getenv(key)
        if value is None:
            if default is not None:
                return default
            raise ValueError(f"{key} not set")
        return int(value)
    except ValueError:
        print(f"ERROR: {key} environment variable is missing or invalid.")
        sys.exit(1)

def get_env_str(key):
    value = os.getenv(key)
    if not value:
        print(f"ERROR: {key} environment variable is missing.")
        sys.exit(1)
    return value

# Required environment variables
NOTIFY_USER_ID = get_env_int("NOTIFY_USER_ID")
DATABASE_URL = get_env_str("DATABASE_URL")
DISCORD_BOT_TOKEN = get_env_str("DISCORD_BOT_TOKEN")

# Optional environment variables with defaults
DISCORD_CHANNEL_ID = get_env_int("DISCORD_CHANNEL_ID", default=0)


#IN GAME SETTINGS

# Paycheck settings
PAYCHECK_AMOUNT = 10_000
PAYCHECK_COOLDOWN_SECONDS = 12 * 3600  # 12 hours in seconds

# Categories game settings
CATEGORIES = ["Foods", "Animals", "Countries"]  # add your real categories if needed

# Categories game timeout
GAME_RESPONSE_TIMEOUT = 10  # seconds to wait for user response in categories game

# Max guesses for riddle or other games (if applicable)
MAX_GUESSES = 5

# Message colors for embeds (optional convenience constants)
from discord import Color
COLOR_GREEN = Color.green()
COLOR_RED = Color.red()
COLOR_ORANGE = Color.orange()
COLOR_TEAL = Color.teal()
