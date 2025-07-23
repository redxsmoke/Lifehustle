import random
from discord.ui import View, Button
import discord
import asyncio
from utilities import reward_user, charge_user

class SneakInMiniGameView(View):
    def __init__(self, user_id, multiplier=1.0, pool=None):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.multiplier = multiplier
        self.pool = pool
        self.lanes = ["left", "middle", "right"]
        self.current_lane = random.choice(self.lanes)
        self.step = 0
        self.failed = False
        self.passed = False
        self.result_message = ""
        self._interaction = None
        self._timeout_task = None

        self.left_button = Button(label="⬅️ Left", style=discord.ButtonStyle.primary)
        self.right_button = Button(label="➡️ Right", style=discord.ButtonStyle.primary)
        self.left_button.callback = self.on_left_click
        self.right_button.callback = self.on_right_click
        self.add_item(self.left_button)
        self.add_item(self.right_button)

        self.predicament_data = [
            {"title": "Avoid the security cameras!", "emoji": "🎥", "fail_actor": "a security camera", "reason": "being spotted by security"},
            {"title": "Avoid your coworkers!", "emoji": "🧍‍♀️", "fail_actor": "a nosy coworker", "reason": "an awkward water cooler chat"},
            {"title": "Avoid your bosses!", "emoji": "👔", "fail_actor": "your boss", "reason": "a surprise performance review"},
            {"title": "Avoid the janitor's mop bucket!", "emoji": "🧹", "fail_actor": "the janitor", "reason": "spilling dirty water everywhere"},
        ]

        self.obstacle_lanes = self.generate_obstacles_for_all()

    def generate_obstacles_for_all(self):
        result = []
        for _ in self.predicament_data:
            safe_lane = random.choice(self.lanes)
            obstacles = [lane for lane in self.lanes if lane != safe_lane]
            random.shuffle(obstacles)
            result.append(obstacles)
        return result

    async def start_step(self, message: discord.Message):
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

        if self.step >= len(self.predicament_data):
            self.passed = True
            reward_amount = 1000 * self.multiplier
            try:
                await reward_user(self.pool, self.user_id, reward_amount)
            except Exception as e:
                print(f"[ERROR] reward_user failed: {e}")
            self.result_message = f"You quietly slipped into your desk and earned ${reward_amount:,.2f}! 🎉"
            await self._message.edit(embed=self.get_embed(), view=None)
            self.stop()
            return

        self._message = message
        await message.edit(embed=self.get_embed(), view=self)
        self._timeout_task = asyncio.create_task(self._timeout())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_left_click(self, interaction: discord.Interaction):
        await self.handle_move(interaction, "left")

    async def on_right_click(self, interaction: discord.Interaction):
        await self.handle_move(interaction, "right")

    async def handle_move(self, interaction: discord.Interaction, move: str):
        self._interaction = interaction
        idx = self.lanes.index(self.current_lane)

        if move == "left" and idx > 0:
            self.current_lane = self.lanes[idx - 1]
        elif move == "right" and idx < 2:
            self.current_lane = self.lanes[idx + 1]

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def _timeout(self):
        await asyncio.sleep(10)
        if self.is_finished():
            return

        obstacles = self.obstacle_lanes[self.step]
        safe = self.current_lane not in obstacles

        if safe:
            self.step += 1
            if self.step >= len(self.predicament_data):
                self.passed = True
                self.result_message = "You made it in undetected. Nice work! 🕶️"
                await self._message.edit(embed=self.get_embed(), view=None)
                self.stop()
            else:
                await self.start_step(self._message)
        else:
            self.failed = True
            penalty_amount = 1000 * self.multiplier
            try:
                await charge_user(self.pool, self.user_id, penalty_amount)
            except Exception as e:
                print(f"[ERROR] charge_user failed: {e}")

            pred = self.predicament_data[self.step]
            self.result_message = (
                f"You were caught by {pred['fail_actor']} in the {', '.join(obstacles)} lane(s)! 💥\n"
                f"You’ve been flagged for {pred['reason']}."
            )
            await self._message.edit(embed=self.get_embed(), view=None)
            self.stop()

    def get_embed(self):
        if self.failed:
            title = "❌ Caught Sneaking In!"
        elif self.passed:
            title = "✅ You Snuck In!"
        else:
            title = self.predicament_data[self.step]["title"]

        desc = self.result_message if (self.failed or self.passed) else self.build_obstacle_scene(self.step)
        page = f"{self.step + 1}/4" if not (self.failed or self.passed) else ""
        color = discord.Color.green() if self.passed else discord.Color.red() if self.failed else discord.Color.dark_gray()

        embed = discord.Embed(title=title, description=desc, color=color)
        if page:
            embed.set_footer(text=page)
        return embed

    def is_finished(self):
        return self.failed or self.passed or self.step >= len(self.predicament_data)

    def build_obstacle_scene(self, step):
        lanes = self.lanes
        user_lane = self.current_lane
        obstacles = self.obstacle_lanes[step]
        obstacle_emoji = self.predicament_data[step]["emoji"]
        safe_emojis = ["📎", "🔇", "🚪", "📤", "🕶️"]

        top_row = " ".join(obstacle_emoji if lane in obstacles else random.choice(safe_emojis) for lane in lanes)
        bottom_row = " ".join("🧍" if lane == user_lane else "⬛" for lane in lanes)

        return f"{top_row}\n{bottom_row}"


async def sneak_in_late_game(ctx, user_id, pool):
    view = SneakInMiniGameView(user_id=user_id, pool=pool)
    message = await ctx.followup.send(embed=view.get_embed(), view=view)
    await view.start_step(message)
    await view.wait()
    return {
        "result": "win" if view.passed else "fail" if view.failed else "neutral",
        "bonus": 500 if view.passed else -250,
        "message": view.result_message or "",
        "dock": 0,
        "penalty": 250 if view.failed else 0,
    }
