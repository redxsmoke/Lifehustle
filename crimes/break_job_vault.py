import discord 
import random
from datetime import timedelta, datetime

COLOR_PRIMARY = 0x5865F2  # Discord blurple

class VaultGame:
    def __init__(self):
        self.code = [random.randint(0, 9) for _ in range(3)]
        self.attempts = 0
        self.max_attempts = 5
        print(f"[DEBUG][VaultGame] New game started with code: {self.code}")

    def check_guess(self, guess_str):
        self.attempts += 1
        print(f"[DEBUG][VaultGame] Checking guess #{self.attempts}: {guess_str}")

        if len(guess_str) != 3 or not guess_str.isdigit():
            print("[DEBUG][VaultGame] Invalid guess format.")
            return "❌ Invalid guess. Enter a 3-digit code like `382`."

        guess = [int(d) for d in guess_str]
        clues = []

        for i in range(3):
            if guess[i] == self.code[i]:
                clues.append("✅")
            elif guess[i] in self.code:
                clues.append("⚠️")
            else:
                clues.append("❌")

        if guess == self.code:
            print("[DEBUG][VaultGame] Guess matched code! Vault unlocked.")
            return "unlocked"
        elif self.attempts >= self.max_attempts:
            print("[DEBUG][VaultGame] Max attempts reached. Locked out.")
            return "locked_out"
        else:
            clue_str = ' '.join(clues)
            print(f"[DEBUG][VaultGame] Guess clues: {clue_str}")
            return f"Attempt {self.attempts}/{self.max_attempts}: {clue_str}"

class VaultGameView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.game = VaultGame()
        self.outcome = None
        self.snitched = False
        self.hide_used = False
        self.snitch_disabled = False
        print(f"[DEBUG][VaultGameView] View created for user_id: {user_id}")

        self.hide_spots = [
            ("🗄️", "behind the storage shelves"),
            ("🧺", "inside the supply closet"),
            ("🪑", "under the desk"),
            ("🛠️", "in the maintenance room"),
            ("📦", "behind the delivery crates"),
            ("🚪", "inside the loading dock"),
            ("📦", "under a pile of boxes"),
            ("🧥", "behind the office curtains"),
            ("🗑️", "inside the trash bin"),
            ("🔥", "in the boiler room"),
            ("🧣", "behind the coat rack"),
            ("🌬️", "inside the ventilation duct"),
        ]

    @discord.ui.button(label="Enter Safe Code", style=discord.ButtonStyle.blurple)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your vault to crack!", ephemeral=True)
            return
        await interaction.response.send_modal(VaultGuessModal(view=self))

    @discord.ui.button(label="Snitch", style=discord.ButtonStyle.red)
    async def snitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.snitch_disabled:
            await interaction.response.send_message("Too slow! You didn't see nuthin'! 🕵️‍♂️", ephemeral=True)
            return

        if interaction.user.id == self.user_id:
            embed = discord.Embed(
                title="🚫 Nope!",
                description="Snitching on yourself? You can't do that 🚫",
                color=0xF04747
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        print(f"[DEBUG][VaultGameView] Snitch attempt by user_id: {interaction.user.id}")
        view = SnitchConfirmView(parent=self)
        await interaction.response.send_message(
            content="Are you sure you want to snitch?",
            view=view,
            ephemeral=True
        )

    async def disable_snitch_button_later(self, message: discord.Message):
        await discord.utils.sleep_until(datetime.utcnow() + timedelta(seconds=10))
        self.snitch_disabled = True
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Snitch":
                child.disabled = True
        try:
            await message.edit(view=self)
            print("[DEBUG][VaultGameView] Snitch button disabled after 10 seconds.")
        except Exception as e:
            print(f"[ERROR][VaultGameView] Failed to disable snitch button: {e}")

    async def show_hide_button(self, interaction: discord.Interaction):
        try:
            view = HideOnlyView(self)
            await interaction.followup.send(
                content="🚨 Alarm Triggered!\nYou failed to crack the vault. Police are on their way to this location! 🚓",
                view=view,
            )
        except Exception as e:
            print(f"[ERROR][VaultGameView] Failed to send hide button message: {e}")

    async def process_police_search(self, interaction: discord.Interaction, chosen_spot: str):
        searched_spots = random.sample(self.hide_spots, 3)
        caught = False

        print("[DEBUG][VaultGameView] Starting police arrival delay (5s)...")
        await asyncio.sleep(5)
        print("[DEBUG][VaultGameView] Sending police arrival message.")
        await interaction.followup.send("🚨 The police have arrived on scene...", ephemeral=True)

        for emoji, spot in searched_spots:
            print(f"[DEBUG][VaultGameView] Sleeping 5s before searching {spot}")
            await asyncio.sleep(5)
            print(f"[DEBUG][VaultGameView] Searching {spot}")
            await interaction.followup.send(f"🔍 The police search **{spot}**...", ephemeral=True)
            if spot == chosen_spot:
                caught = True
                print(f"[DEBUG][VaultGameView] Match found! Robber hiding in {spot}")
                break
            else:
                print(f"[DEBUG][VaultGameView] {spot} is clear.")

        print("[DEBUG][VaultGameView] Final 5s delay before outcome...")
        await asyncio.sleep(5)

        if caught:
            await interaction.followup.send(f"🚨 The police found you hiding **{chosen_spot}**! You're arrested and fired!", ephemeral=True)
            print(f"[DEBUG][VaultGameView] User {interaction.user.id} caught hiding in {chosen_spot}")

            try:
                async with interaction.client.pool.acquire() as conn:
                    await conn.execute("UPDATE user_finances SET checking_account_balance = 0 WHERE user_id = $1", interaction.user.id)
                    await conn.execute("UPDATE users SET occupation_id = NULL WHERE user_id = $1", interaction.user.id)
                    await conn.execute(
                        "INSERT INTO user_criminal_record (user_id, date_of_offense, crime_id, crime_description, class) VALUES ($1, NOW(), 1, 'Theft', 'Misdemeanor')",
                        interaction.user.id
                    )
                print(f"[DEBUG][VaultGameView] Arrest DB updates completed for user {interaction.user.id}")
            except Exception as e:
                print(f"[ERROR][VaultGameView] Error during arrest DB update: {e}")
        else:
            await interaction.followup.send("🎉 The police searched everywhere but couldn’t find you. You evaded capture!", ephemeral=True)
            print(f"[DEBUG][VaultGameView] User {interaction.user.id} evaded police successfully")

        self.stop()
        print("[DEBUG][VaultGameView] View stopped.")


class HideOnlyView(discord.ui.View):
    def __init__(self, vault_view: VaultGameView):
        super().__init__(timeout=120)
        self.vault_view = vault_view
        # Add only Hide button enabled here
        self.hide_button = discord.ui.Button(label="Hide", style=discord.ButtonStyle.green)
        self.hide_button.callback = self.on_hide_click
        self.add_item(self.hide_button)

    async def on_hide_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.vault_view.user_id:
            await interaction.response.send_message("You can’t hide if you weren’t robbing the vault. 👀", ephemeral=True)
            return
        # Prevent multiple clicks
        self.hide_button.disabled = True
        await interaction.response.edit_message(content="Preparing hide options...", view=None)

        # Send the hide spots choices as an ephemeral followup message
        choices = random.sample(self.vault_view.hide_spots, 4)

        class HideChoiceView(discord.ui.View):
            def __init__(self, vault_view: VaultGameView):
                super().__init__(timeout=60)
                self.vault_view = vault_view
                self.chosen_spot = None

                for emoji, description in choices:
                    label = f"{emoji} {description}"
                    self.add_item(HideChoiceButton(label=label, vault_view=vault_view, parent_view=self, description=description))

        class HideChoiceButton(discord.ui.Button):
            def __init__(self, label: str, vault_view: VaultGameView, parent_view: discord.ui.View, description: str):
                super().__init__(label=label, style=discord.ButtonStyle.green)
                self.vault_view = vault_view
                self.parent_view = parent_view
                self.description = description

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.vault_view.user_id:
                    await interaction.response.send_message("Only the robber can pick a hiding spot.", ephemeral=True)
                    return

                self.parent_view.chosen_spot = self.description
                await interaction.response.edit_message(content=f"You chose to hide **{self.description}**. Waiting for police to arrive...", view=None)

                # Run police search after user picks
                await self.vault_view.process_police_search(interaction, self.description)
                self.vault_view.stop()
                self.parent_view.stop()


        hide_choice_view = HideChoiceView(self.vault_view)
        await interaction.followup.send("Choose a place to hide:", view=hide_choice_view, ephemeral=True)

class VaultGuessModal(discord.ui.Modal, title="🔐 Enter Vault Code"):
    guess_input = discord.ui.TextInput(label="Enter 3-digit code", max_length=3)

    def __init__(self, view: VaultGameView):
        super().__init__()
        self.view = view
        print(f"[DEBUG][VaultGuessModal] Modal initialized for user_id: {self.view.user_id}")

    async def on_submit(self, interaction: discord.Interaction):
        print(f"[DEBUG][VaultGuessModal] Guess submitted by user_id: {interaction.user.id} with value: {self.guess_input.value}")
        result = self.view.game.check_guess(self.guess_input.value)
        embed = discord.Embed(color=COLOR_PRIMARY)

        try:
            if result == "unlocked":
                self.view.outcome = "success"
                embed.title = "💰 Vault Cracked!"
                embed.description = "You escaped with the loot!"
                await interaction.response.edit_message(content=None, embed=embed, view=None)
                self.view.stop()

            elif result == "locked_out":
                self.view.outcome = "failure"
                embed.title = "🔒 Too Many Failed Attempts"
                code_str = ''.join(map(str, self.view.game.code))
                embed.description = f"You were caught! The code was `{code_str}`."
                await interaction.response.edit_message(content=None, embed=embed, view=None)
                await self.view.show_hide_button(interaction)
                self.view.stop()

            else:
                embed.title = "Vault Code Guess"
                embed.description = result
                await interaction.response.edit_message(content=None, embed=embed, view=self.view)

        except Exception as e:
            print(f"[ERROR][VaultGuessModal] Error responding to guess: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred processing your guess.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred processing your guess.", ephemeral=True)
            except Exception as inner_e:
                print(f"[ERROR][VaultGuessModal] Failed to send error message: {inner_e}")

class SnitchConfirmView(discord.ui.View):
    def __init__(self, parent: VaultGameView):
        super().__init__(timeout=15)
        self.parent = parent

    @discord.ui.button(label="Report to Police", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.parent.outcome = "snitched"
        self.parent.snitched = True
        self.parent.stop()

        embed = discord.Embed(
            title="🚨 Police Alerted!",
            description="You snitched on the suspect! The police are on their way to this location! 👮",
            color=0xF04747
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        print(f"[DEBUG][SnitchConfirmView] Snitched by {interaction.user.id}")

        try:
            await self.parent.show_hide_button(interaction)
        except Exception as e:
            print(f"[ERROR][SnitchConfirmView] Failed to show hide button after snitch: {e}")

    @discord.ui.button(label="I ain't no snitch", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Respect. 👏", view=None)
        print(f"[DEBUG][SnitchConfirmView] {interaction.user.id} backed out of snitching.")
