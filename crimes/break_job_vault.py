import discord
import random

COLOR_PRIMARY = 0x5865F2  # Discord blurple, adjust if you want

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
        super().__init__(timeout=60)
        self.robber_id = user_id
        self.outcome = None
        self.snitched = False
        self.code = [random.randint(0, 9) for _ in range(3)]
        self.attempts = 0

    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.green)
    async def enter_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.robber_id:
            await interaction.response.send_message("You can't crack this vault. You're not the one robbing it.", ephemeral=True)
            return
        # Vault cracking logic...
        # set self.outcome = "success" or "failure" accordingly
        self.stop()

    @discord.ui.button(label="Snitch", style=discord.ButtonStyle.danger)
    async def snitch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        snitch_view = SnitchConfirmView(self)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚨 Snitch?",
                description="Do you want to alert the police and shut this down?",
                color=0xFF5555
            ),
            view=snitch_view,
            ephemeral=True
        )

class SnitchConfirmView(discord.ui.View):
    def __init__(self, vault_view):
        super().__init__()
        self.vault_view = vault_view

    @discord.ui.button(label="Report to Police", style=discord.ButtonStyle.red)
    async def confirm_snitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.vault_view.snitched = True
        self.vault_view.outcome = "failure"
        self.vault_view.stop()
        await interaction.response.send_message("🚨 You snitched. Police have been alerted.", ephemeral=True)

    @discord.ui.button(label="I ain't no snitch", style=discord.ButtonStyle.gray)
    async def cancel_snitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🫡 Good choice.", ephemeral=True)
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
                print("[DEBUG][VaultGuessModal] Vault unlocked, game ended.")

            elif result == "locked_out":
                self.view.outcome = "failure"
                embed.title = "🔒 Too Many Failed Attempts"
                code_str = ''.join(map(str, self.view.game.code))
                embed.description = f"You were caught! The code was `{code_str}`."
                await interaction.response.edit_message(content=None, embed=embed, view=None)
                self.view.stop()
                print("[DEBUG][VaultGuessModal] Locked out, game ended.")

            else:
                embed.title = "Vault Code Guess"
                embed.description = result
                await interaction.response.edit_message(content=None, embed=embed, view=self.view)
                print("[DEBUG][VaultGuessModal] Guess clues sent, game continues.")
        except Exception as e:
            print(f"[ERROR][VaultGuessModal] Error responding to guess: {e}")
            # Attempt to send error message if response is not done yet
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred processing your guess.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred processing your guess.", ephemeral=True)
            except Exception as inner_e:
                print(f"[ERROR][VaultGuessModal] Failed to send error message: {inner_e}")
