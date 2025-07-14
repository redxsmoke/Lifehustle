import discord

class CrimeSelectionView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot
        self.add_item(CrimeDropdown(self))
        print(f"[DEBUG][CrimeSelectionView] Initialized for user {user} ({user.id})")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_user = interaction.user.id == self.user.id
        if not is_user:
            print(f"[DEBUG][CrimeSelectionView] Interaction check failed for user {interaction.user} ({interaction.user.id})")
        return is_user

class CrimeDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="Theft", description="Steal from someone or somewhere"),
        ]
        super().__init__(placeholder="Select a crime...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        crime_choice = self.values[0]
        print(f"[DEBUG][CrimeDropdown] User {interaction.user} selected crime: {crime_choice}")

        if crime_choice == "Theft":
            await interaction.response.edit_message(
                content="Where do you want to steal from?",
                view=TheftLocationView(self.parent_view.user, self.parent_view.bot),
                embed=None
            )
        else:
            await interaction.response.send_message("Crime not implemented yet.", ephemeral=True)

class TheftLocationView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot
        self.add_item(TheftLocationDropdown(self))
        print(f"[DEBUG][TheftLocationView] Initialized for user {user} ({user.id})")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_user = interaction.user.id == self.user.id
        if not is_user:
            print(f"[DEBUG][TheftLocationView] Interaction check failed for user {interaction.user} ({interaction.user.id})")
        return is_user

class TheftLocationDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(label="Rob your job", description="Steal from your workplace"),
        ]
        super().__init__(placeholder="Select location...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        location = self.values[0]
        print(f"[DEBUG][TheftLocationDropdown] User {interaction.user} selected location: {location}")

        if location == "Rob your job":
            cog = self.parent_view.bot.get_cog("CrimeCommands")
            if cog:
                try:
                    print(f"[DEBUG][TheftLocationDropdown] Passing interaction to CrimeCommands.handle_rob_job for user {interaction.user}")
                    await cog.handle_rob_job(interaction)
                except Exception as e:
                    print(f"❌ Error in handle_rob_job: {e}")
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.send_message("❌ Something went wrong during the robbery attempt.", ephemeral=True)
                        else:
                            await interaction.followup.send("❌ Something went wrong during the robbery attempt.", ephemeral=True)
                    except Exception as inner_e:
                        print(f"❌ Failed to send error message: {inner_e}")
            else:
                print("❌ CrimeCommands cog not found!")
                await interaction.response.send_message("⚠️ Crime system not available. (Cog missing)", ephemeral=True)
        else:
            await interaction.response.send_message("Location not implemented yet.", ephemeral=True)

class ConfirmRobberyView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.value = None
        self.user_interaction = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        print(f"[DEBUG][interaction_check] Received interaction from {interaction.user.id}")
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your robbery.", ephemeral=True)
            print(f"[DEBUG] Blocked interaction from user {interaction.user.id} not matching {self.user_id}")
            return False
        return True

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG][ConfirmRobberyView] Continue button clicked.")
        self.value = True
        self.user_interaction = interaction
        await interaction.response.send_message("✅ Robbery confirmed!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG][ConfirmRobberyView] Cancel button clicked.")
        self.value = False
        self.user_interaction = interaction
        await interaction.response.send_message("❌ Robbery cancelled.", ephemeral=True)
        self.stop()
