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
            "behind the storage shelves", "inside the supply closet", "under the desk",
            "in the maintenance room", "behind the delivery crates", "inside the loading dock",
            "under a pile of boxes", "behind the office curtains", "inside the trash bin",
            "in the boiler room", "behind the coat rack", "inside the ventilation duct"
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

    async def show_hide_button(self, interaction: discord.Interaction, reason: str = "snitched"):
        class HideButton(discord.ui.Button):
            def __init__(self, vault_view: VaultGameView):
                super().__init__(label="Hide", style=discord.ButtonStyle.green)
                self.vault_view = vault_view  # renamed from self.view

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.vault_view.user_id:
                    await interaction.response.send_message("You can’t hide if you weren’t robbing the vault. 👀", ephemeral=True)
                    return

                if self.vault_view.hide_used:
                    await interaction.response.send_message("You’ve already tried hiding!", ephemeral=True)
                    return

                self.vault_view.hide_used = True
                chosen_spot = random.choice(self.vault_view.hide_spots)
                await self.vault_view.process_hide_choice(interaction, chosen_spot)

        alert_text = {
            "snitched": "🚨 Police Alerted!\nSomeone snitched! The police are on their way to this location! 👮",
            "failed": "🚨 Alarm Triggered!\nYou failed to crack the vault. Police are on their way to this location! 🚓"
        }

        new_view = discord.ui.View(timeout=30)
        new_view.add_item(HideButton(self))

        try:
            await interaction.followup.send(
                content=alert_text.get(reason, "🚨 Police have been notified."),
                view=new_view
            )
        except Exception as e:
            print(f"[ERROR][VaultGameView] Failed to send hide button message: {e}")

    async def process_hide_choice(self, interaction: discord.Interaction, chosen_spot: str):
        await interaction.followup.send(f"You hid {chosen_spot}... waiting for the police to arrive...", ephemeral=True)
        evade = random.choices([True, False], weights=[60, 40])[0]

        if evade:
            await interaction.followup.send("🎉 Great work! You evaded the police by becoming one with your hideout!", ephemeral=True)
            print(f"[DEBUG][VaultGameView] User {interaction.user.id} evaded police successfully.")
        else:
            await interaction.followup.send(f"🚨 The police searched {chosen_spot} and found you! You're arrested and fired!", ephemeral=True)
            print(f"[DEBUG][VaultGameView] User {interaction.user.id} failed to evade police. Penalizing user...")

            async with interaction.client.pool.acquire() as conn:
                await conn.execute("UPDATE user_finances SET checking_account_balance = 0 WHERE user_id = $1", interaction.user.id)
                await conn.execute("UPDATE users SET occupation_id = NULL WHERE user_id = $1", interaction.user.id)
                await conn.execute(
                    "INSERT INTO user_criminal_record (user_id, date_of_offense, crime_id, crime_description, class) VALUES ($1, NOW(), 1, 'Theft', 'Misdemeanor')",
                    interaction.user.id
                )

        self.stop()

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
                await self.view.show_hide_button(interaction, reason="failed")
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
            await self.parent.show_hide_button(interaction, reason="snitched")
        except Exception as e:
            print(f"[ERROR][SnitchConfirmView] Failed to show hide button after snitch: {e}")

    @discord.ui.button(label="I ain't no snitch", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Respect. 👏", view=None)
        print(f"[DEBUG][SnitchConfirmView] {interaction.user.id} backed out of snitching.")
