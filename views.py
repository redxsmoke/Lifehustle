import datetime
import random
import discord
from discord.ui import View, Button

import utilities 
import vehicle_logic 
from db_user import get_user, upsert_user
from globals import pool


# COMMUTE BUTTONS VIEW
class CommuteButtons(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None  # Will hold the message with buttons

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="commute_drive")
    async def drive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "drive")

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="commute_bike")
    async def bike_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "bike")

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="commute_subway")
    async def subway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "subway")

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="commute_bus")
    async def bus_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "bus")

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Commute selection timed out. Please try again.",
                    view=self
                )
            except Exception as e:
                print(f"[ERROR] Failed to edit message on timeout: {e}")


# TRANSPORTATION SHOP BUTTONS VIEW
class TransportationShopButtons(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Buy Bike 🚴", style=discord.ButtonStyle.success, custom_id="buy_bike")
    async def buy_bike(self, interaction: discord.Interaction, button: Button):
        try:
            color = random.choice(BIKE_COLORS)
            condition = "Pristine"
            bike_item = {
                "type": "Bike",
                "color": color,
                "condition": condition,
                "purchase_date": datetime.date.today().isoformat(),
                "commute_count": 0
            }
            await handle_vehicle_purchase(interaction, item=bike_item, cost=2000)
        except Exception:
            await interaction.response.send_message("🚫 Failed to buy Bike. Try again later.", ephemeral=True)

    @discord.ui.button(label="Buy Beater Car 🚙", style=discord.ButtonStyle.primary, custom_id="buy_blue_car")
    async def buy_blue_car(self, interaction: discord.Interaction, button: Button):
        try:
            plate = generate_random_plate()
            color = random.choice(CAR_COLORS)
            car_item = {
                "type": "Beater Car",
                "plate": plate,
                "color": color,
                "condition": "Heavily Used",
                "commute_count": 0,
                "purchase_date": datetime.date.today().isoformat()
            }
            await handle_vehicle_purchase(interaction, item=car_item, cost=10000)
        except Exception:
            await interaction.response.send_message("🚫 Failed to buy Beater Car. Try again later.", ephemeral=True)

    # Add other car buttons similarly...


# SELL FROM STASH VIEW
class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_confirmation = {}  # Tracks items awaiting confirmation keyed by custom_id

        for vehicle in vehicles:
            custom_id = f"sell_{vehicle.get('tag', vehicle.get('plate', id(vehicle)))}"
            btn = Button(
                label=self.make_button_label(vehicle),
                style=discord.ButtonStyle.danger,
                custom_id=custom_id
            )
            btn.callback = self.make_sell_request_callback(vehicle, custom_id)
            self.add_item(btn)

    def make_button_label(self, item):
        emoji = {
            "Bike": "🚴",
            "Beater Car": "🚙",
            "Sedan Car": "🚗",
            "Sports Car": "🏎️",
            "Pickup Truck": "🛻"
        }.get(item["type"], "❓")
        desc = item.get("tag") or item.get("color", "Unknown")
        cond = item.get("condition", "Unknown")

        base_prices = {
            "Bike": 2000,
            "Beater Car": 10000,
            "Sedan Car": 25000,
            "Sports Car": 100000,
            "Pickup Truck": 75000
        }
        resale_percent = {
            "Pristine": 0.85,
            "Lightly Used": 0.50,
            "Heavily Used": 0.25,
            "Rusted": 0.10
        }
        base_price = base_prices.get(item["type"], 0)
        percent = resale_percent.get(cond, 0.10)
        resale = int(base_price * percent)

        return f"Sell {emoji} {desc} ({cond}) - ${resale:,}"

    def make_sell_request_callback(self, item, custom_id):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your stash.", ephemeral=True)
                return

            # Save pending item to confirm keyed by custom_id
            self.pending_confirmation[custom_id] = item

            # Disable all buttons except the one clicked
            for child in self.children:
                child.disabled = True

            # Confirm and Cancel buttons
            confirm_btn = Button(label="Confirm Sale", style=discord.ButtonStyle.success, custom_id=f"confirm_{custom_id}")
            cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id=f"cancel_{custom_id}")

            async def confirm_callback(i: discord.Interaction):
                await self.confirm_sale(i, item, custom_id)

            async def cancel_callback(i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("This isn't your stash.", ephemeral=True)
                    return
                # Restore original buttons
                self.clear_items()
                for vehicle in self.vehicles:
                    cid = f"sell_{vehicle.get('tag', vehicle.get('plate', id(vehicle)))}"
                    btn = Button(
                        label=self.make_button_label(vehicle),
                        style=discord.ButtonStyle.danger,
                        custom_id=cid
                    )
                    btn.callback = self.make_sell_request_callback(vehicle, cid)
                    self.add_item(btn)
                await i.response.edit_message(content="Sale cancelled.", view=self)

            confirm_btn.callback = confirm_callback
            cancel_btn.callback = cancel_callback

            self.clear_items()
            self.add_item(confirm_btn)
            self.add_item(cancel_btn)

            await interaction.response.edit_message(
                content=f"Are you sure you want to sell your {item['type']} ({item.get('color', 'Unknown')}, {item.get('condition', 'Unknown')})?",
                view=self
            )
        return callback

    async def confirm_sale(self, interaction: discord.Interaction, item, custom_id):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return

        user = await get_user(pool, self.user_id)
        if not user:
            await interaction.response.send_message("You don’t have an account yet.", ephemeral=True)
            return

        condition = item.get("condition", "Unknown")
        base_prices = {
            "Bike": 2000,
            "Beater Car": 10000,
            "Sedan Car": 25000,
            "Sports Car": 100000,
            "Pickup Truck": 75000
        }
        resale_percent = {
            "Pristine": 0.85,
            "Lightly Used": 0.50,
            "Heavily Used": 0.25,
            "Rusted": 0.10
        }

        base_price = base_prices.get(item["type"], 0)
        percent = resale_percent.get(condition, 0.10)
        resale = int(base_price * percent)

        inventory = user.get("inventory", [])

        def is_same_vehicle(v):
            if not isinstance(v, dict):
                return False
            if "plate" in item and "plate" in v and item["plate"] == v["plate"]:
                return True
            if "tag" in item and "tag" in v and item["tag"] == v["tag"]:
                return True
            return v == item  # fallback exact dict match

        new_inventory = [v for v in inventory if not is_same_vehicle(v)]

        if len(new_inventory) == len(inventory):
            await interaction.response.send_message(
                "❌ That item is no longer in your stash.",
                ephemeral=True
            )
            return

        user["inventory"] = new_inventory
        user["checking_account"] += resale
        await upsert_user(pool, self.user_id, user)

        self.clear_items()
        await interaction.response.edit_message(
            content=f"✅ You sold your {item['type']} for ${resale:,} ({condition}).",
            view=None
        )


# GROCERY CATEGORY VIEW (pagination)
class GroceryCategoryView(View):
    def __init__(self, pages, user_id, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages  # List of tuples: (category_title, items_list)
        self.user_id = user_id
        self.current_page = 0
        self.message = None

        # Pagination buttons
        self.previous_button.disabled = True
        if len(pages) <= 1:
            self.next_button.disabled = True

        # Load buttons for the first page
        self.load_page_buttons()

    def load_page_buttons(self):
        # Remove all existing item buttons first (except prev/next)
        for child in list(self.children):
            if getattr(child, "custom_id", None) and child.custom_id not in ("previous", "next"):
                self.remove_item(child)

        # Add buttons for current page items
        _, items = self.pages[self.current_page]
        for item in items:
            btn = Button(
                label=f"{item['emoji']} {item['name']} - ${item['price']}",
                style=discord.ButtonStyle.primary,
                custom_id=f"buy_{item['id']}"
            )
            btn.callback = self.make_purchase_callback(item)
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your shop to use.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    def _get_embed(self):
        title, items = self.pages[self.current_page]
        desc = "\n".join(f"{item['emoji']} {item['name']} - ${item['price']}" for item in items)
        embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")
        return embed

    async def send(self, interaction: discord.Interaction):
        embed = self._get_embed()
        self.message = await interaction.followup.send(embed=embed, view=self)

    def make_purchase_callback(self, item):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                return

            user = await get_user(pool, self.user_id)
            if user is None:
                await interaction.response.send_message("You don't have an account yet.", ephemeral=True)
                return

            balance = user.get("checking_account", 0)
            if balance < item["price"]:
                await interaction.response.send_message(
                    f"🚫 You don't have enough money to buy {item['emoji']} {item['name']}.",
                    ephemeral=True
                )
                return

            # Deduct price and add to inventory
            user["checking_account"] -= item["price"]
            inventory = user.get("inventory", [])
            inventory.append(f"{item['emoji']} {item['name']}")
            user["inventory"] = inventory

            await upsert_user(pool, self.user_id, user)

            await interaction.response.send_message(
                f"✅ You bought {item['emoji']} {item['name']} for ${item['price']:,}!",
                ephemeral=True
            )
        return callback

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="previous")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            button.disabled = self.current_page == 0
            self.next_button.disabled = False
            self.load_page_buttons()
            embed = self._get_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            button.disabled = self.current_page == len(self.pages) - 1
            self.previous_button.disabled = False
            self.load_page_buttons()
            embed = self._get_embed()
            await interaction.response.edit_message(embed=embed, view=self)


# GROCERY STASH PAGINATION VIEW
class GroceryStashPaginationView(View):
    def __init__(self, user_id, embeds, timeout=120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.embeds = embeds
        self.current_page = 0
        self.message = None

        # Disable prev button on first page
        self.previous_button.disabled = True
        if len(embeds) <= 1:
            self.next_button.disabled = True

    async def send(self, interaction: discord.Interaction):
        self.message = await interaction.followup.send(embed=self.embeds[self.current_page], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your inventory view.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="stash_previous")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            button.disabled = self.current_page == 0
            self.next_button.disabled = False
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="stash_next")
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            button.disabled = self.current_page == len(self.embeds) - 1
            self.previous_button.disabled = False
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

class SubmitWordModal(discord.ui.Modal, title="Submit a new word"):
    def __init__(self, category: str):
        super().__init__()
        self.category = category

        self.word_input = discord.ui.TextInput(
            label="Enter your word",
            placeholder="Type your word here...",
            max_length=100,
        )
        self.add_item(self.word_input)

    async def on_submit(self, interaction: discord.Interaction):
        word_raw = self.word_input.value.strip()

        # Confirm to submitter
        await interaction.response.send_message(
            f"✅ Thanks for your submission of '{word_raw}' in category '{self.category}'. Your word will be reviewed by a moderator.",
            ephemeral=True
        )

        # Notify the moderator by DM
        notify_user = interaction.client.get_user(NOTIFY_USER_ID)
        if notify_user:
            try:
                await notify_user.send(
                    f"📢 New word submission:\n"
                    f"User: {interaction.user} ({interaction.user.id})\n"
                    f"Category: {self.category}\n"
                    f"Word: {word_raw}"
                )
            except Exception as e:
                print(f"[ERROR] Failed to send DM to {NOTIFY_USER_ID}: {e}")
        else:
            print(f"[ERROR] Could not find user with ID {NOTIFY_USER_ID} to send DM.")