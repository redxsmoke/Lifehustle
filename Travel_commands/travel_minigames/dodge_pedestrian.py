import random
from discord.ui import View, Button
import discord
import asyncio

class TravelMiniGameView(View):
    def __init__(self, user_id, multiplier=1.0):
        super().__init__(timeout=10)  # 10 seconds per prompt
        self.user_id = user_id
        self.multiplier = multiplier
        self.current_lane = random.choice(["left", "middle", "right"])
        self.step = 0
        self.failed = False
        self.passed = False
        self.result_message = ""
        self._interaction = None
        self._timeout_task = None

        # Create buttons
        self.left_button = Button(label="⬅️ Left", style=discord.ButtonStyle.primary)
        self.right_button = Button(label="➡️ Right", style=discord.ButtonStyle.primary)
        self.left_button.callback = self.on_left_click
        self.right_button.callback = self.on_right_click
        self.add_item(self.left_button)
        self.add_item(self.right_button)

        # List of predicament methods, shuffled to randomize order
        self.predicaments = [
            self.predicament_1,
            self.predicament_2,
            self.predicament_3,
            self.predicament_4
        ]
        random.shuffle(self.predicaments)

        self.obstacle_lanes = [None] * len(self.predicaments)

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
            else:
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
                self.reset_timeout()

    def reset_timeout(self):
        if hasattr(self, "_timeout_task") and self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()

        self._timeout_task = asyncio.create_task(self._timeout())

    async def _timeout(self):
        await asyncio.sleep(10)
        if not self.is_finished():
            self.failed = True
            self.result_message = "⏰ Timeout! You didn’t respond in time and hit an obstacle."
            if self._interaction:
                await self._interaction.edit_original_response(embed=self.get_embed(), view=None)
            self.stop()

    def get_embed(self):
        if self.failed:
            return discord.Embed(
                title="Mini-game Failed!",
                description=self.result_message,
                color=discord.Color.red()
            )
        elif self.passed:
            return discord.Embed(
                title="Mini-game Complete!",
                description=self.result_message,
                color=discord.Color.green()
            )

        return discord.Embed(
            title="Avoid the Obstacles",
            description=self.build_obstacle_scene(self.step),
            color=discord.Color.blurple()
        ).set_footer(
            text=f"Current lane: {self.current_lane.capitalize()} | You have 10 seconds to respond"
        )

    def build_obstacle_scene(self, step):
        obstacle_emoji = self.get_obstacle_emoji(step)
        lanes = ["🛣️", "🛣️", "🛣️"]
        car_lane = {"left": 0, "middle": 1, "right": 2}[self.current_lane]
        obstacle_lanes = self.obstacle_lanes[step] or []

        for lane in obstacle_lanes:
            i = {"left": 0, "middle": 1, "right": 2}[lane]
            lanes[i] = obstacle_emoji

        obstacle_row = " ".join(lanes)
        car_row = "   " * car_lane + "🚗"

        return f"{obstacle_row}\n{car_row}"

    def get_obstacle_emoji(self, step):
        if step == 0:
            return "🧒"
        elif step == 1:
            return "👵"
        elif step == 2:
            return "🏐"
        else:
            return "🚧"  # cones

    async def predicament_1(self, user_lane, idx):
        kid_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [kid_lane]

        if user_lane == kid_lane:
            return False, f"You hit the kid in the {kid_lane} lane! 💥"
        return True, ""

    async def predicament_2(self, user_lane, idx):
        grandma_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [grandma_lane]

        if user_lane == grandma_lane:
            return False, f"You hit grandma in the {grandma_lane} lane! 💥"
        return True, ""

    async def predicament_3(self, user_lane, idx):
        ball_lane = random.choice(["left", "middle", "right"])
        self.obstacle_lanes[idx] = [ball_lane]

        if user_lane == ball_lane:
            return False, f"You ran over the ball in the {ball_lane} lane! 💥"
        return True, ""

    async def predicament_4(self, user_lane, idx):
        possible_pairs = [["left", "middle"], ["left", "right"], ["middle", "right"]]
        obstacles = random.choice(possible_pairs)
        self.obstacle_lanes[idx] = obstacles

        safe_lane = next(l for l in ["left", "middle", "right"] if l not in obstacles)
        if user_lane != safe_lane:
            return False, f"You hit roadwork cones in the {obstacles[0]} and {obstacles[1]} lanes! 💥"
        return True, ""


    def predicament_text(self, step, current_lane):
        lanes = self.obstacle_lanes[step]
        if lanes is None:
            return "Loading..."

        # Format lane(s) for description
        if len(lanes) == 1:
            lane_desc = lanes[0]
            if step == 0:
                return (
                    f"A kid runs in the **{lane_desc} lane**. You are in the **{current_lane} lane**. "
                    f"Move out of the {lane_desc} lane to avoid hitting the kid."
                )
            elif step == 1:
                return (
                    f"A grandma stands in the **{lane_desc} lane**. You are in the **{current_lane} lane**. "
                    f"Stay out of the {lane_desc} lane to avoid her."
                )
            elif step == 2:
                return (
                    f"A ball rolls in the **{lane_desc} lane**. You are in the **{current_lane} lane**. "
                    f"Avoid the {lane_desc} lane to keep your ride smooth."
                )
        elif len(lanes) == 2:
            lane_desc = " and ".join(lanes)
            return (
                f"Two obstacles block the **{lane_desc} lanes**. "
                f"You must pick the only safe lane (not blocked) to avoid crashing."
            )
        else:
            return "Unknown predicament..."
