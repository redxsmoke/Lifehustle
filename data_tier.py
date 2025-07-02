async def seed_grocery_types(pool):
    category_map = {
        "produce": 1,
        "dairy": 2,
        "protein": 3,
        "snacks": 4,
        "beverages": 5,
    }

    grocery_types = [
        {"name": "Apple", "emoji": "🍎", "cost": 3, "category": "produce"},
        {"name": "Banana", "emoji": "🍌", "cost": 2, "category": "produce"},
        {"name": "Carrot", "emoji": "🥕", "cost": 4, "category": "produce"},
        {"name": "Tomato", "emoji": "🍅", "cost": 3, "category": "produce"},
        {"name": "Potato", "emoji": "🥔", "cost": 2, "category": "produce"},
        {"name": "Corn", "emoji": "🌽", "cost": 3, "category": "produce"},
        {"name": "Cheese", "emoji": "🧀", "cost": 6, "category": "dairy"},
        {"name": "Milk", "emoji": "🥛", "cost": 4, "category": "dairy"},
        {"name": "Ice Cream", "emoji": "🍦", "cost": 5, "category": "dairy"},
        {"name": "Frozen Yogurt", "emoji": "🍨", "cost": 5, "category": "dairy"},
        {"name": "Chicken Leg", "emoji": "🍗", "cost": 10, "category": "protein"},
        {"name": "Steak", "emoji": "🥩", "cost": 15, "category": "protein"},
        {"name": "Ribs", "emoji": "🍖", "cost": 12, "category": "protein"},
        {"name": "Shrimp", "emoji": "🍤", "cost": 14, "category": "protein"},
        {"name": "Eggs (dozen)", "emoji": "🥚", "cost": 4, "category": "protein"},
        {"name": "Popcorn", "emoji": "🍿", "cost": 3, "category": "snacks"},
        {"name": "Chocolate Bar", "emoji": "🍫", "cost": 4, "category": "snacks"},
        {"name": "Cookie", "emoji": "🍪", "cost": 2, "category": "snacks"},
        {"name": "Donut", "emoji": "🍩", "cost": 3, "category": "snacks"},
        {"name": "French Fries", "emoji": "🍟", "cost": 5, "category": "snacks"},
        {"name": "Coffee", "emoji": "☕", "cost": 4, "category": "beverages"},
        {"name": "Tea", "emoji": "🍵", "cost": 3, "category": "beverages"},
        {"name": "Soda", "emoji": "🥤", "cost": 3, "category": "beverages"},
        {"name": "Beer", "emoji": "🍺", "cost": 6, "category": "beverages"},
        {"name": "Wine", "emoji": "🍷", "cost": 12, "category": "beverages"},
    ]

    async with pool.acquire() as conn:
        for item in grocery_types:
            category_id = category_map[item["category"].lower()]
            await conn.execute(
                """
                INSERT INTO cd_grocery_type (name, category_id, cost, emoji)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO NOTHING
                """,
                item["name"],
                category_id,
                item["cost"],
                item["emoji"],
            )
    print("✅ Seeded grocery types with emojis, categories, and costs.")
