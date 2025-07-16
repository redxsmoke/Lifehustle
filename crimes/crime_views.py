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
            pool = self.parent_view.bot.pool  # or use globals.pool if needed
            user_id = interaction.user.id

            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT current_location FROM users WHERE user_id = $1", user_id)

            if not row or row["current_location"] != 1:
                embed = discord.Embed(
                    title="📍 Wrong Location",
                    description="❌ You need to travel to **Work** before you can rob your job.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Proceed if user is at work
            cog = self.parent_view.bot.get_cog("CrimeCommands")
            if cog:
                try:
                    print(f"[DEBUG][TheftLocationDropdown] Passing interaction to CrimeCommands.handle_rob_job for user {interaction.user}")
                    await cog.handle_rob_job(interaction)
                except Exception as e:
                    print(f"❌ Error in handle_rob_job: {e}")
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                embed=discord.Embed(
                                    title="❌ Robbery Failed",
                                    description="Something went wrong during the robbery attempt.",
                                    color=discord.Color.red()
                                ),
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="❌ Robbery Failed",
                                    description="Something went wrong during the robbery attempt.",
                                    color=discord.Color.red()
                                ),
                                ephemeral=True
                            )
                    except Exception as inner_e:
                        print(f"❌ Failed to send error message: {inner_e}")
            else:
                print("❌ CrimeCommands cog not found!")
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="⚠️ Crime System Unavailable",
                        description="Crime system is not available right now. Please try again later.",
                        color=discord.Color.orange()
                    ),
                    ephemeral=True
                )

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

        embed = discord.Embed(
            title="✅ Robbery Confirmed!",
            description="You're moving forward with the heist. Let's crack the vault...",
            color=0x43B581  # Green
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG][ConfirmRobberyView] Cancel button clicked.")
        self.value = False
        self.user_interaction = interaction

        embed = discord.Embed(
            title="❌ Robbery Cancelled",
            description="You've backed out. Maybe next time...",
            color=0xF04747  # Red
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
