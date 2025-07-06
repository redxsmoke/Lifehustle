import discord

class ConfirmResignView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who invoked the command to interact
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This confirmation isn't for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm Resign", style=discord.ButtonStyle.danger)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        await interaction.response.edit_message(content="Resignation confirmed.", view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        await interaction.response.edit_message(content="Resignation cancelled.", view=None)
        self.stop()
