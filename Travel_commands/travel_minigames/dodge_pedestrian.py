import random
from discord.ui import View, Button
import discord
import asyncio

class TravelMiniGameView(View):
    def __init__(self, user_id, multiplier=1.0):
        super().__init__(timeout=10)
        self.user_id = user_id
        self.multiplier = multiplier
        self.current_lane = random.choice(["left", "middle", "right"])
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

        self.obstacle_lanes = [None] * len(self.predicaments)

    async def _initialize_obstacles(self):
        # Initialize obstacles once for each predicament to keep consistency
        for idx, predicament in enumerate(self.predicaments):
            await predicament(self.current_lane, idx)

    async def start_step(self, message: discord.Message):
        # Initialize obstacles once on first step
        if self.step == 0:
            await self._initialize_obstacles()

        if self.step >= len(self.predicaments):
            self.passed = True
            self.result_message = "You safely navigated all obstacles! 🎉"
            await message.edit(embed=self.get_embed(), view=None)
            self.stop()
            return

        await message.edit(embed=self.get_embed(), view=self)
        self.reset_timeout()  # Reset timeout timer each step

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_left_click(self, interaction: discord.Interaction):
        await self.handle_move(interaction, "left")

    async def on_right_click(self, interaction: discord.Interaction):
        await self.handle_move(interaction, "right")

    async def handle_move(self, interaction: discord.Interaction, move: str):
        self._interaction = interaction

        lane_order = ["left", "middle", "right"]
        idx = lane_order.index(self.current_lane)

        if move == "left" and idx > 0:
            new_lane = lane_order[idx - 1]
        elif move == "right" and idx < 2:
            new_lane = lane_order[idx + 1]
        else:
            new_lane = self.current_lane

        result, msg = await self.predicaments[self.step](new_lane, self.step)

        if not result:
            self.failed = True
            self.result_message = msg
            await interaction.response.edit_message(embed=self.get_embed(), view=None)
            self.stop()
            return
        else:
            self.current_lane = new_lane
            self.step += 1

            if self.step >= len(self.predicaments):
                self.passed = True
                self.result_message = "You safely navigated all obstacles! 🎉"
                await interaction.response.edit_message(embed=self.get_embed(), view=None)
                self.stop()
                return
            else:
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
                self.reset_timeout()   # Make sure to reset timeout here!

    def reset_timeout(self):
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        self._timeout_task = asyncio.create_task(self._timeout())

    async def _timeout(self):
        await asyncio.sleep(10)
        if not self.is_finished():
            # Check if the current lane is safe for this predicament
            is_safe, _ = await self.predicaments[self.step](self.current_lane, self.step)

            if is_safe:
                # Safe lane, so advance to next step automatically
                self.step += 1

                if self.step >= len(self.predicaments):
                    self.passed = True
                    self.result_message = "You safely navigated all obstacles! 🎉"
                    if self._interaction:
                        await self._interaction.edit_original_response(embed=self.get_embed(), view=None)
                    self.stop()
                else:
                    if self._interaction:
                        await self.start_step(await self._interaction.original_response())
            else:
                # Unsafe lane with no response = fail
                self.failed = True
                self.result_message = "⏰ Timeout! You didn’t respond in time and hit an obstacle."
                if self._interaction:
                    await self._interaction.edit_original_response(embed=self.get_embed(), view=None)
                self.stop()

    def is_finished(self):
        return self.failed or self.passed or self.step >= len(self.predicaments)

    def build_obstacle_scene(self, step):
        road = "🛣️"
        car = "🚗"
        spacing = "     "
        lanes = ["left", "middle", "right"]

        obstacles = self.obstacle_lanes[step]
        if not obstacles:
            return f"{road}{road}{road}\n{car}"

        icons = {
            0: "🧒",
            1: "👵",
            2: "⚽",
            3: "🚧",
        }

        obstacle_char = icons.get(step, "🧱")

        top = ""
        for lane in lanes:
            top += obstacle_char if lane in obstacles else road

        bottom = ""
        for lane in lanes:
            bottom += car if lane == self.current_lane else spacing

        return f"{top}\n{bottom}"

    async def predicament_1(self, user_lane, idx):
        kid_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [kid_lane]
        return (user_lane != kid_lane), f"You hit the kid in the {kid_lane} lane! 💥"

    async def predicament_2(self, user_lane, idx):
        grandma_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [grandma_lane]
        return (user_lane != grandma_lane), f"You hit grandma in the {grandma_lane} lane! 💥"

    async def predicament_3(self, user_lane, idx):
        ball_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [ball_lane]
        return (user_lane != ball_lane), f"You ran over the ball in the {ball_lane} lane! 💥"

    async def predicament_4(self, user_lane, idx):
        possible_pairs = [["left", "middle"], ["left", "right"], ["middle", "right"]]
        obstacles = random.choice(possible_pairs)
        self.obstacle_lanes[idx] = obstacles
        safe_lane = next(l for l in ["left", "middle", "right"] if l not in obstacles)
        return (user_lane == safe_lane), f"You hit obstacles in lanes {obstacles[0]} and {obstacles[1]}! 💥"

    async def on_timeout(self):
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        if not self.is_finished():
            self.failed = True
            self.result_message = "⏰ Timeout! You didn’t respond in time and lost the game."
            if self._interaction:
                await self._interaction.edit_original_response(embed=self.get_embed(), view=None)
            self.stop()
