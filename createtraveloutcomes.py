import os
import asyncio
import asyncpg

# Create the table if it doesn't exist
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cd_travel_summaries (
    id SERIAL PRIMARY KEY,
    travel_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    effect_amount INTEGER DEFAULT 0,
    effect_type VARCHAR(20) DEFAULT 'neutral',
    probability FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Set probabilities per effect_type
weight_map = {
    "neutral": 0.5,
    "negative": 0.25,
    "positive": 0.25
}
seed_data = {
    "car": {
        "negative": [
            ("Your car's AC broke down and now you sweat like a sauna. -$100", -100, "loss"),
            ("You got a ticket for 'excessive eyebrow raising' at a stoplight. -$75", -75, "loss"),
            ("You ran over a squirrel... it was the mayor's pet. -$500 fine", -500, "loss"),
            ("Your GPS sent you into a lake. Towed your car out. -$350", -350, "loss"),
            ("Your car radio only plays 'Baby Shark' on repeat. Mental damage: priceless.", 0, "neutral"),
            ("Hit a pothole and now your tire has a flat. -$60", -60, "loss"),
            ("Gas prices soared during your trip. Ouch. -$40", -40, "loss"),
            ("Your car smells like gym socks. No fine, just sorry.", 0, "neutral"),
            ("Your windshield wipers decided to retire mid-ride. -$30 for new ones", -30, "loss"),
            ("You got lost and ended up at a clown convention. Wallet -$20 (facepalm)", -20, "loss"),
        ],
        "positive": [
            ("Found $20 on the floor of your car! Jackpot!", 20, "gain"),
            ("Your car's radio played your favorite song twice. Mood +100.", 0, "neutral"),
            ("Traffic was so light, you set a personal speed record (legal, mostly).", 0, "neutral"),
            ("Your car got a mysterious wax job. Smells amazing!", 0, "neutral"),
            ("You got a free coffee from a drive-thru employee for being nice.", 0, "neutral"),
            ("A pigeon took a nap on your hood. Instant celebrity.", 0, "neutral"),
            ("Your car won 'best smell' in a random parking lot contest. +$50 prize", 50, "gain"),
            ("Found a $5 bill wedged in the seat cushions. Sweet!", 5, "gain"),
            ("Car washed itself in a sudden rain shower. Nature’s gift.", 0, "neutral"),
            ("Your car stereo played a surprise free concert. Priceless.", 0, "neutral"),
        ],
        "neutral": [
            ("Your car drove exactly as expected. Boring but reliable.", 0, "neutral"),
            ("You honked at a pedestrian who totally ignored you. Awkward.", 0, "neutral"),
            ("Passed a billboard advertising tacos. Craving initiated.", 0, "neutral"),
            ("The traffic light turned green exactly when you arrived. Luck?", 0, "neutral"),
            ("Your car’s dashboard smells faintly of vanilla. Weird but nice.", 0, "neutral"),
            ("Saw a red car just like yours. Mirror image vibes.", 0, "neutral"),
            ("Your GPS suggested a scenic route. Took it, no regrets.", 0, "neutral"),
            ("Radio played ads but you zoned out. Brain survival mode.", 0, "neutral"),
            ("Your car seat felt extra comfy today. Small joys.", 0, "neutral"),
            ("Nothing happened, and that's... okay.", 0, "neutral"),
        ],
    },
    "bike": {
        "negative": [
            ("A bird decided your helmet was a landing pad. Gross.", 0, "neutral"),
            ("You hit a pothole and nearly kissed the pavement. -$10 band-aids", -10, "loss"),
            ("Some kid yelled 'slowpoke!' as you pedaled uphill. Burned ego.", 0, "neutral"),
            ("Your bike chain snapped mid-ride. Walked home. -$40 repairs", -40, "loss"),
            ("A dog chased you. Lost your water bottle. -$15", -15, "loss"),
            ("Someone stole your bike seat. They have good taste.", 0, "neutral"),
            ("You got a flat tire on a trail with no phone signal. Oof.", 0, "neutral"),
            ("You forgot your helmet and now you’re paranoid. Buy a new one? -$50", -50, "loss"),
            ("Rode into a swarm of angry bees. Emergency pit stop.", 0, "neutral"),
            ("You wiped out in front of a cafe. Instant fame. Wallet -$20", -20, "loss"),
        ],
        "positive": [
            ("Found $20 tucked inside your bike’s frame. Lucky you!", 20, "gain"),
            ("Your bike bell sounded like music today. Neighbors applauded.", 0, "neutral"),
            ("Breeze was perfect, and your legs felt like rocket boosters.", 0, "neutral"),
            ("Discovered a new shortcut that saves 5 minutes! Efficiency!", 0, "neutral"),
            ("A friendly dog followed you for a mile. Instant buddy.", 0, "neutral"),
            ("You passed a group and they cheered for you. MVP status.", 0, "neutral"),
            ("Your bike tire magically fixed itself. Okay, probably not.", 0, "neutral"),
            ("Saw a double rainbow while biking. Priceless.", 0, "neutral"),
            ("You found a $5 bill caught on a fence. Score!", 5, "gain"),
            ("Your legs thanked you after the ride. Fitness bonus.", 0, "neutral"),
        ],
        "neutral": [
            ("The ride was exactly as expected: nothing weird happened.", 0, "neutral"),
            ("You nodded politely at a jogger who ignored you. Social skills?", 0, "neutral"),
            ("Passed a mysterious graffiti wall. Artistic vibes.", 0, "neutral"),
            ("Your water bottle stayed put. Small wins.", 0, "neutral"),
            ("You remembered to lock your bike this time. Progress.", 0, "neutral"),
            ("Bike light flickered but stayed on. Ghost mode.", 0, "neutral"),
            ("Saw a squirrel. It stared at you. Mutual respect.", 0, "neutral"),
            ("Your favorite song came on your headphones. Motivation!", 0, "neutral"),
            ("You avoided a puddle expertly. Ninja moves.", 0, "neutral"),
            ("Nothing exciting happened. Chill ride.", 0, "neutral"),
        ],
    },
    "bus": {
        "negative": [
            ("The bus smelled like 3-day-old cheese. You survived.", 0, "neutral"),
            ("Your stop got skipped. Extra walk, -$5 Uber.", -5, "loss"),
            ("A stranger loudly argued with the driver. Drama overload.", 0, "neutral"),
            ("You sat next to someone who didn’t stop talking. Earplugs needed.", 0, "neutral"),
            ("Bus AC broke down. Instant sauna experience.", 0, "neutral"),
            ("Missed your bus by 1 second. Rage quit.", 0, "neutral"),
            ("Lost your phone while getting on. Recovered, barely.", 0, "neutral"),
            ("Your bus card was declined. Had to pay cash. -$3", -3, "loss"),
            ("A toddler threw snacks everywhere. You were the cleanup crew.", 0, "neutral"),
            ("Driver took a mysterious detour. Adventure or mistake?", 0, "neutral"),
        ],
        "positive": [
            ("You scored a seat near the window. Views for days!", 0, "neutral"),
            ("Got off at the right stop on the first try. Win!", 0, "neutral"),
            ("A fellow passenger gave you a candy bar. Sweet!", 0, "neutral"),
            ("The bus driver complimented your shoes. Confidence boost.", 0, "neutral"),
            ("You found $10 in your jacket pocket while riding. Jackpot!", 10, "gain"),
            ("Bus was on time. Shocking but delightful.", 0, "neutral"),
            ("Listened to a killer podcast episode on the way.", 0, "neutral"),
            ("A dog hopped on the bus. Instant mood lifter.", 0, "neutral"),
            ("You met a new friend while waiting. Social butterfly.", 0, "neutral"),
            ("Bus wifi actually worked. Miracle!", 0, "neutral"),
        ],
        "neutral": [
            ("Nothing but smooth stops and starts. Solid trip.", 0, "neutral"),
            ("You counted the number of seats. Lost count at 42.", 0, "neutral"),
            ("Saw a billboard for a weird movie. Tempting...", 0, "neutral"),
            ("Bus horn honked somewhere nearby. Classic.", 0, "neutral"),
            ("You rehearsed your grocery list mentally. Productive!", 0, "neutral"),
            ("Checked your watch. Time flies on the bus.", 0, "neutral"),
            ("Bus smelled faintly of coffee. Invigorating.", 0, "neutral"),
            ("You avoided eye contact with the creeper. Skill.", 0, "neutral"),
            ("The bus driver sang quietly to themselves. Charming.", 0, "neutral"),
            ("Nothing unexpected happened. Solid bus ride.", 0, "neutral"),
        ],
    },
    "subway": {
        "negative": [
            ("Your train car smelled like old gym socks. Hold your breath!", 0, "neutral"),
            ("You missed your stop and had to double back. Oops.", 0, "neutral"),
            ("The subway was delayed by 20 minutes. Rage level: high.", 0, "neutral"),
            ("Someone dropped their phone and it bounced under the seats.", 0, "neutral"),
            ("You accidentally pressed the emergency stop. Sorry, everyone.", 0, "neutral"),
            ("Your headphone cable got caught in the door. Painful.", 0, "neutral"),
            ("A stranger loudly took a phone call about their cat. Drama.", 0, "neutral"),
            ("Train was packed. Personal space? Never heard of it.", 0, "neutral"),
            ("Your shoe got stepped on twice. Vengeance is sweet.", 0, "neutral"),
            ("Someone spilled coffee on your jacket. Free makeover?", 0, "neutral"),
        ],
        "positive": [
            ("Found a $20 bill stuck under the seat. Sweet!", 20, "gain"),
            ("You snagged a seat on a crowded train. Victory dance.", 0, "neutral"),
            ("Saw a subway musician killing it on their guitar. Inspiring!", 0, "neutral"),
            ("Train arrived early. Even the subway gods approve.", 0, "neutral"),
            ("Your phone battery survived the ride. Rare success.", 0, "neutral"),
            ("Met a cool person who recommended a great book.", 0, "neutral"),
            ("You caught the express train. Fast and furious.", 0, "neutral"),
            ("Got free subway WiFi and binge-watched a show. Productivity?", 0, "neutral"),
            ("You got a free coffee from a random stranger. Warm fuzzies.", 0, "neutral"),
            ("The subway lights flickered artistically. Modern art?", 0, "neutral"),
        ],
        "neutral": [
            ("Subway ride was just... subway ride. Nothing weird.", 0, "neutral"),
            ("Listened to the usual screeches and bangs. Nostalgic?", 0, "neutral"),
            ("The train stopped exactly on time. Precision!", 0, "neutral"),
            ("You mentally rehearsed your day. Efficient!", 0, "neutral"),
            ("Saw a rat. Did not engage. Win!", 0, "neutral"),
            ("You avoided eye contact with everyone. Classic subway move.", 0, "neutral"),
            ("Headphones in, world out. Survival mode.", 0, "neutral"),
            ("Your stop announcement was crystal clear. Rare treat.", 0, "neutral"),
            ("Saw an ad for pineapple pizza. Contemplated life choices.", 0, "neutral"),
            ("Nothing unexpected. Just another subway trip.", 0, "neutral"),
        ],
    },
}

async def main(pool=None):
    created_pool = False

    if pool is None:
        db_user = os.getenv("PGUSER") or os.getenv("DATABASE_USER") or "postgres"
        db_pass = os.getenv("PGPASSWORD") or os.getenv("DATABASE_PASSWORD") or ""
        db_name = os.getenv("PGDATABASE") or os.getenv("DATABASE_NAME") or "yourdb"
        db_host = os.getenv("PGHOST") or os.getenv("DATABASE_HOST") or "localhost"
        db_port = os.getenv("PGPORT") or os.getenv("DATABASE_PORT") or "5432"

        pool = await asyncpg.create_pool(
            user=db_user,
            password=db_pass,
            database=db_name,
            host=db_host,
            port=int(db_port)
        )
        created_pool = True

    async with pool.acquire() as conn:
        print("✅ Creating table cd_travel_summaries...")
        await conn.execute(CREATE_TABLE_SQL)

        print("✅ Seeding data into cd_travel_summaries...")

        insert_query = """
            INSERT INTO cd_travel_summaries 
            (travel_type, description, effect_amount, effect_type, probability) 
            VALUES ($1, $2, $3, $4, $5)
        """

        for travel_type, categories in seed_data.items():
            for effect_cat, entries in categories.items():
                prob = weight_map.get(effect_cat, 1.0)
                for desc, amount, eff_type in entries:
                    await conn.execute(
                        insert_query,
                        travel_type,
                        desc,
                        amount,
                        eff_type,
                        prob
                    )

        print("✅ Done seeding cd_travel_summaries!")

    if created_pool:
        await pool.close()

# Allows the script to be run directly
if __name__ == "__main__":
    asyncio.run(main())