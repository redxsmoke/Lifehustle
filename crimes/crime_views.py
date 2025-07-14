import discord

class CrimeSelectionView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot
        self.add_item(CrimeDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

class CrimeDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="Theft", description="Steal from someone or somewhere"),
            # Add more crimes later here
        ]
        super().__init__(placeholder="Select a crime...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        crime_choice = self.values[0]
        if crime_choice == "Theft":
            await interaction.response.edit_message(
                content="Where do you want to steal from?",
                view=TheftLocationView(self.parent_view.user, self.parent_view.bot)
            )
        else:
            await interaction.response.send_message("Crime not implemented yet.", ephemeral=True)

class TheftLocationView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot
        self.add_item(TheftLocationDropdown(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

class TheftLocationDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="Rob your job", description="Steal from your workplace"),
            # Add more locations here later
        ]
        super().__init__(placeholder="Select location...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        location = self.values[0]
        if location == "Rob your job":
            cog = self.parent_view.bot.get_cog("CrimeCommands")
            if cog:
                await cog.handle_rob_job(interaction)
            else:
                await interaction.response.send_message(
                    "⚠️ Crime system not available.", ephemeral=True
                )
        else:
            await interaction.response.send_message("Location not implemented yet.", ephemeral=True)
