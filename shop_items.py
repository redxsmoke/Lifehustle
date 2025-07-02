import json

def load_shop_items():
    with open("shop_items.json", "r", encoding="utf-8") as f:
        return json.load(f)

SHOP_ITEMS = load_shop_items()
