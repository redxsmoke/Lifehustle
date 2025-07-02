import json

def load_categories():
    with open("categories.json", "r") as f:
        data = json.load(f)
    return data.get("Foods", {})


import json

def load_shop_items():
    with open("shop_items.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data  # returns the entire JSON data (list or dict depending on your file)
