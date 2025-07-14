import discord
import random

class VaultGame:
    def __init__(self):
        self.code = [random.randint(0, 9) for _ in range(3)]
        self.attempts = 0
        self.max_attempts = 5

    def check_guess(self, guess_str):
        self.attempts += 1
        if len(guess_str) != 3 or not guess_str.isdigit():
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
            return "unlocked"
        elif self.attempts >= self.max_attempts:
            return "locked_out"
        else:
            return f"Attempt {self.attempts}/5: {' '.join(clues)}"


class VaultGameView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.game = VaultGame()
        self.outcome = None

    @discord.ui.button(label="Submit Guess", style=discord.ButtonStyle.blurple)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your vault to crack!", ephemeral=True)
            return

        modal = VaultGuessModal(view=self)
        await interaction.response.send_modal(modal)


class VaultGuessModal(discord.ui.Modal, title="🔐 Enter Vault Code"):
    guess_input = discord.ui.TextInput(label="Enter 3-digit code", max_length=3)

    def __init__(self, view: VaultGameView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        result = self.view.game.check_guess(self.guess_input.value)

        if result == "unlocked":
            self.view.outcome = "success"
            await interaction.response.edit_message(
                content="💰 Vault cracked! You escaped with the loot!",
                view=None
            )
            self.view.stop()

        elif result == "locked_out":
            self.view.outcome = "failure"
            await interaction.response.edit_message(
                content=f"🔒 Too many failed attempts. You were caught! The code was `{''.join(map(str, self.view.game.code))}`.",
                view=None
            )
            self.view.stop()

        else:
            await interaction.response.send_message(result, ephemeral=True)
