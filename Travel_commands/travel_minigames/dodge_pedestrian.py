import random
from discord.ui import View, Button
import discord
import asyncio
from utilities import reward_user, charge_user
from globals import pool

class TravelMiniGameView(View):
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
                self.result_message = "You safely navigated all obstacles! 🎉"
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
                f"You hit {obstacle_name} in the {', '.join(obstacles)} lane{'s' if len(obstacles) > 1 else ''}! 💥\n"
                f"You were fined ${penalty_amount:,.2f} for {fine_reason}"
            )

            await self._message.edit(embed=self.get_embed(), view=None)
            self.stop()


    def get_failure_details(self, step, obstacles):
        obstacle_names = {
            0: "the kid",
            1: "grandma",
            2: "the ball",
            3: "the roadworks",
        }

        funny_fines = {
            0: "their missing homework excuses",
            1: "grandma's hip replacement surgery",
            2: "the new soccer ball fund",
            3: "the city's repair budget",
        }

        name = obstacle_names.get(step, "an obstacle")
        fine = funny_fines.get(step, "emergency repairs")

        return name, fine

    def get_embed(self):
        title = "❌ Avoid the Obstacles" if self.failed else (
            "✅ Avoid the Obstacles" if self.passed else "🕹️ Avoid the Obstacles"
        )
        desc = self.result_message if (self.failed or self.passed) else self.build_obstacle_scene(self.step)
        page = f"{self.step+1}/4" if not (self.failed or self.passed) else ""

        color = discord.Color.green() if self.passed else (discord.Color.red() if self.failed else discord.Color.blurple())

        embed = discord.Embed(title=title, description=desc, color=color)
        if page:
            embed.set_footer(text=page)
        return embed


    def is_finished(self):
        return self.failed or self.passed or self.step >= len(self.predicaments)

    def build_obstacle_scene(self, step):
        road = "🛣️"
        car = "🚗"
        empty = "⬛"

        obstacles = self.obstacle_lanes[step]
        icons = {
            0: "🧒",
            1: "👵",
            2: "⚽",
            3: "🚧",
        }
        obstacle_char = icons.get(step, "🧱")
        top = " ".join(obstacle_char if lane in obstacles else road for lane in self.lanes)
        bottom = " ".join(car if lane == self.current_lane else empty for lane in self.lanes)

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
