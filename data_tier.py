# ✅ Seeds the grocery types
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


# ✅ Seeds the grocery categories
async def seed_grocery_categories(pool):
    grocery_categories = [
        ("Produce", "🍎"),
        ("Dairy", "🥛"),
        ("Protein", "🍗"),
        ("Snacks", "🍿"),
        ("Beverages", "🥤"),
    ]

    async with pool.acquire() as conn:
        for name, emoji in grocery_categories:
            await conn.execute(
                """
                INSERT INTO cd_grocery_category (name, emoji)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING
                """,
                name,
                emoji,
            )
    print("✅ Seeded grocery categories with emojis.")


async def drop_vehicle_appearence_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS cd_vehicle_appearence;")
        print("✅ Dropped cd_vehicle_appearence table.")


async def create_vehicle_appearance_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cd_vehicle_appearance (
                cd_vehicle_appearance_id SERIAL PRIMARY KEY,
                description TEXT NOT NULL,
                condition_id INT NOT NULL REFERENCES cd_vehicle_condition(condition_id),
                vehicle_type_id INT NOT NULL REFERENCES cd_vehicle_type(vehicle_type_id)
            );
        """)
        print("✅ Created cd_vehicle_appearance table.")




async def seed_vehicle_appearance(pool):
    vehicle_descriptions = {
        1: {  # Beater Car
            1: [
                "Somehow this clunker came straight off the used lot sparkling.",
                "Fresh coat of paint hides its true identity — for now.",
                "Tires still have tread, and all the windows roll up!",
                "The upholstery is clean and smells like... hope?",
                "Surprisingly responsive acceleration — for a beater."
            ],
            2: [
                "One headlight slightly foggy, but everything works.",
                "A few paint chips, but overall roadworthy.",
                "Minor exhaust rattle when idle.",
                "Slight dent in the trunk, adds character.",
                "Interior held together by good intentions and duct tape."
            ],
            3: [
                "Rims mismatched but functional.",
                "Roof lining sags slightly in the back.",
                "AC makes weird noises but still blows air.",
                "Rear seatbelt jammed — don't sit back there.",
                "Shakes a bit over 45 mph, but it’ll get you there."
            ],
            4: [
                "Missing hubcap and a cracked windshield.",
                "Exhaust sounds like a growling raccoon.",
                "Interior is 60% seat, 40% crumbs.",
                "Rearview mirror fell off but is in the glove box.",
                "Steering pulls to the left... aggressively."
            ],
            5: [
                "Starts only on Tuesdays if the moon is right.",
                "Passenger door won’t open — or close, depending on mood.",
                "Dashboard lit up like a Christmas tree.",
                "Floorboards are suspiciously soft.",
                "Smells like burning regret and old burgers."
            ]
        },
        2: {  # Sedan
            1: [
                "Paint gleams like it belongs to a manager of the month.",
                "Cruises quietly — like a whisper down the road.",
                "Seats are immaculate with plastic still on the floor.",
                "Steering smooth like melted butter.",
                "Everything clicks and glows like it’s fresh off the lot."
            ],
            2: [
                "Minor scratches from suburban parking lots.",
                "Air freshener doing its best against kid snacks.",
                "Drives smooth with occasional brake squeak.",
                "Just enough wear to show it's dependable.",
                "Still turns heads at a PTA meeting."
            ],
            3: [
                "Trunk has old receipts and a weird stain.",
                "Sun visor mirror cracked but still usable.",
                "Interior could use a vacuum and a prayer.",
                "Paint faded slightly on roof and hood.",
                "Left blinker works... eventually."
            ],
            4: [
                "Back seat stuck in 'baby mode'.",
                "Cigarette burn on driver's seat.",
                "Dash display flickers when it rains.",
                "Hasn't been washed since the last election.",
                "Takes two tries to start, but starts."
            ],
            5: [
                "One wheel looks borrowed from a shopping cart.",
                "Horn stuck on 'meh'.",
                "Trunk rusted shut.",
                "Seats smell like lost ambition.",
                "Rear window taped up from the inside."
            ]
        },
        3: {  # Sports Car
            1: [
                "Paint so glossy it blinds bystanders.",
                "Engine purrs like a caffeinated cheetah.",
                "Zero miles, full throttle.",
                "Racing stripes sharp and symmetrical.",
                "Interior stitched with red leather and arrogance."
            ],
            2: [
                "Slight scuffs near the spoiler from showing off.",
                "Driver’s seat broken in by confidence.",
                "Minor rim rash from aggressive turns.",
                "Still roars at green lights, just not as loud.",
                "Speedometer still dares you to redline."
            ],
            3: [
                "Exhaust rattles like it’s trying too hard.",
                "Scratch down the passenger door — earned.",
                "Paint faded under the hood vents.",
                "Spoiler loose but holding on with pride.",
                "Leather seats cracked but still cocky."
            ],
            4: [
                "Turbo badge faded to ‘turd’.",
                "Front bumper zip-tied after track day.",
                "Cracked dash from sun and speed.",
                "One mirror hanging by a thread of hope.",
                "Gear shifts grind like it holds a grudge."
            ],
            5: [
                "Stalled halfway to the car meet.",
                "Flat rear tire and two warning lights.",
                "Spoiler fell off last week — again.",
                "Smells like clutch and desperation.",
                "Hood held closed with bungee cords."
            ]
        },
        4: {  # Pickup Truck
            1: [
                "Polished chrome and proud stance.",
                "No scratches in the bed — yet.",
                "Tailgate opens smoother than expected.",
                "V8 rumble fresh from the factory.",
                "Cab interior smells like leather and freedom."
            ],
            2: [
                "Scuff marks from weekend hauls.",
                "Mud on the tires but no rust underneath.",
                "One toolbox rattle but solid ride.",
                "Bed liner scratched but intact.",
                "Still hauls without complaints."
            ],
            3: [
                "Dents from helping too many friends move.",
                "Worn tires from backroads and bad ideas.",
                "Paint starting to fade on the hood.",
                "Tailgate squeaks when opened.",
                "Cab smells like old coffee and gear oil."
            ],
            4: [
                "Faded decals and a cracked windshield.",
                "Rust spots forming under the wheel wells.",
                "Passenger door needs a shoulder check to open.",
                "Rear light duct-taped into place.",
                "Shakes when loaded heavy."
            ],
            5: [
                "Won’t reverse without stalling.",
                "Axle clicks when turning left.",
                "Cracked dash and ripped seat covers.",
                "Toolbox padlock rusted shut.",
                "Bed rusted through in one corner."
            ]
        },
        5: {  # Bike
            1: [
                "Fresh chain and high-pressure tires.",
                "Reflectors clean and properly mounted.",
                "Brakes tight and responsive.",
                "No rust, no fuss, just speed.",
                "Seat perfectly cushioned for cruising."
            ],
            2: [
                "Slight dirt on the frame but rides smooth.",
                "Brakes squeak but function great.",
                "Chain clean and oiled.",
                "Handlebar grips show light wear.",
                "Tires evenly worn, still plenty of tread."
            ],
            3: [
                "Rear brake cable needs a little tightening.",
                "Tires slightly underinflated.",
                "Seat has minor tear from overuse.",
                "Spokes slightly misaligned.",
                "Pedals scuffed from city use."
            ],
            4: [
                "Chain rust spotted from outdoor storage.",
                "Gears shift inconsistently.",
                "Seat loose and handlebars sticky.",
                "Rims bent from potholes.",
                "Back fender rattles when riding."
            ],
            5: [
                "Tires flat and dry-rotted.",
                "Chain seized in place.",
                "Brakes don’t bite at all.",
                "Frame scratched, rusted, and bent.",
                "Missing pedal, seat duct-taped in place."
            ]
        },
        6: {  # Motorcycle
            1: [
                "Shiny chrome and purring engine.",
                "Seat pristine and grips unworn.",
                "No scratches — showroom quality.",
                "Exhaust roars with authority.",
                "Clean chain, smooth throttle."
            ],
            2: [
                "Minor bug guts on the front fairing.",
                "Chain slightly worn but responsive.",
                "Brake pads fresh and firm.",
                "Rides smooth with slight vibration.",
                "Windscreen shows light road wear."
            ],
            3: [
                "Engine vibrates more than usual.",
                "Tailpipe discolored from heat.",
                "Front brake squeals slightly.",
                "Fuel gauge inaccurate but working.",
                "Seat foam starting to collapse."
            ],
            4: [
                "Handlebar grip torn and sticky.",
                "Rust around rear shock mount.",
                "Oil stains on crankcase.",
                "Chain slack and dirty.",
                "Headlight dim and flickering."
            ],
            5: [
                "Won’t start without a push.",
                "Muffler rattling and half-disconnected.",
                "Flat tire and rusted spokes.",
                "Exhaust leak near engine.",
                "Frame slightly bent from a tip-over."
            ]
        }
    }

    appearance_id = 1
    async with pool.acquire() as conn:
        for vehicle_type_id, condition_map in vehicle_descriptions.items():
            for condition_id, desc_list in condition_map.items():
                for desc in desc_list:
                    await conn.execute(
                        """
                        INSERT INTO cd_vehicle_appearance (cd_vehicle_appearance_id, description, condition_id, vehicle_type_id)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (cd_vehicle_appearance_id) DO NOTHING;
                        """,
                        appearance_id,
                        desc,
                        condition_id,
                        vehicle_type_id
                    )
                    appearance_id += 1

    print("✅ Seeded cd_vehicle_appearance with 150 rows.")
