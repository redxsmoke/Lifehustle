import random
from discord.ui import View, Button
import discord
import asyncio
from utilities import reward_user, charge_user
from globals import pool

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

        self.predicaments = [
            self.predicament_1,
            self.predicament_2,
            self.predicament_3,
            self.predicament_4
        ]
        random.shuffle(self.predicaments)

        self.obstacle_lanes = []
        for idx in range(len(self.predicaments)):
            self.obstacle_lanes.append(self.generate_obstacles_for_predicament(idx))

    def generate_obstacles_for_predicament(self, idx):
        if idx == 3:
            pairs = [["left", "middle"], ["left", "right"], ["middle", "right"]]
            return random.choice(pairs)
        else:
            return [random.choice(self.lanes)]

    async def start_step(self, message: discord.Message):
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass

        if self.step >= len(self.predicaments):
            self.passed = True
            reward_amount = 1000 * self.multiplier
            try:
                await reward_user(self.pool, self.user_id, reward_amount)
            except Exception as e:
                print(f"[ERROR] reward_user failed: {e}")
            self.result_message = f"You safely navigated all obstacles and earned ${reward_amount:,.2f}! 🎉"
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
        await asyncio.sleep(3)
        if self.is_finished():
            return

        obstacles = self.obstacle_lanes[self.step]
        safe = self.current_lane not in obstacles

        if safe:
            self.step += 1
            if self.step >= len(self.predicaments):
                self.passed = True
                # Removed reward_user call here to avoid double rewards/messages
                self.result_message = "You quietly slipped into your desk. Nobody suspects a thing. 🎯"
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

            obstacle_name, fine_reason = self.get_failure_details(self.step, obstacles)
            self.result_message = (
                f"You were spotted by {obstacle_name} in the {', '.join(obstacles)} lane{'s' if len(obstacles) > 1 else ''}! 💥\n"
                f"You’ve been flagged for {fine_reason}."
            )


            await self._message.edit(embed=self.get_embed(), view=None)
            self.stop()


    def get_failure_details(self, step, obstacles):
        obstacle_names = {
            0: "your boss",
            1: "a nosy coworker",
            2: "a security camera",
            3: "the janitor with a mop bucket",
        }

        funny_fines = {
            0: "getting pulled into a surprise meeting",
            1: "an awkward water cooler chat",
            2: "HR sensitivity training",
            3: "mop-related injury paperwork",
        }

        name = obstacle_names.get(step, "someone")
        fine = funny_fines.get(step, "an internal investigation")

        return name, fine


    def get_embed(self):
        title = "❌ Caught Sneaking In!" if self.failed else (
            "✅ You Snuck In!" if self.passed else "🕵️ Sneak In Late"
        )
        desc = self.result_message if (self.failed or self.passed) else self.build_obstacle_scene(self.step)
        page = f"{self.step+1}/4" if not (self.failed or self.passed) else ""

        color = discord.Color.green() if self.passed else (discord.Color.red() if self.failed else discord.Color.dark_gray())

        embed = discord.Embed(title=title, description=desc, color=color)
        if page:
            embed.set_footer(text=page)
        return embed



    def is_finished(self):
        return self.failed or self.passed or self.step >= len(self.predicaments)

    def build_obstacle_scene(self, step):
        lanes = self.lanes
        user_lane = self.current_lane
        obstacles = self.obstacle_lanes[step]

        obstacle_emojis = {
            0: "👀",   # Boss
            1: "🧍‍♀️", # Coworker
            2: "🎥",   # Security cam
            3: "🧹",   # Janitor
        }
        safe_emojis = ["📎", "🔇", "🚪", "📤", "🕶️"]
        default_obstacle = "🚫"
        obstacle_icon = obstacle_emojis.get(step, default_obstacle)

        top = " ".join(obstacle_icon if lane in obstacles else random.choice(safe_emojis) for lane in lanes)
        bottom = " ".join("🧍" if lane == user_lane else "⬛" for lane in lanes)

        return f"{top}\n{bottom}"

    async def predicament_1(self, user_lane, idx):
        lane = self.obstacle_lanes[idx][0]
        safe = user_lane != lane
        msg = f"You hit the kid in the {lane} lane! 💥" if not safe else ""
        return safe, msg

    async def predicament_2(self, user_lane, idx):
        lane = self.obstacle_lanes[idx][0]
        safe = user_lane != lane
        msg = f"You hit grandma in the {lane} lane! 💥" if not safe else ""
        return safe, msg

    async def predicament_3(self, user_lane, idx):
        lane = self.obstacle_lanes[idx][0]
        safe = user_lane != lane
        msg = f"You ran over the ball in the {lane} lane! 💥" if not safe else ""
        return safe, msg

    async def predicament_4(self, user_lane, idx):
        obstacles = self.obstacle_lanes[idx]
        safe_lane = next(l for l in self.lanes if l not in obstacles)
        safe = user_lane == safe_lane
        msg = f"You hit obstacles in lanes {obstacles[0]} and {obstacles[1]}! 💥" if not safe else ""
        return safe, msg


async def sneak_in_late_game(ctx, user_id, pool):
    view = SneakInMiniGameView(user_id=user_id, pool=pool)

    if hasattr(ctx, "interaction") and ctx.interaction is not None:
        # Use interaction followup
        message = await ctx.interaction.followup.send(embed=view.get_embed(), view=view)
    else:
        # Fallback to normal ctx.send
        message = await ctx.send(embed=view.get_embed(), view=view)

    await view.start_step(message)
    await view.wait()
    return {
        "result": "win" if view.passed else "fail" if view.failed else "neutral",
        "bonus": 500 if view.passed else -250,
        "message": view.result_message or "",
        "dock": 0,
        "penalty": 250 if view.failed else 0,
    }
