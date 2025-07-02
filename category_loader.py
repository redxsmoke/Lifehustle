import json

def load_categories():
    with open("categories.json", "r") as f:
        data = json.load(f)
    return data.get("Foods", {})
