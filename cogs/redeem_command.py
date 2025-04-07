import discord
import uuid
from discord import app_commands
from discord.ext.commands import Cog
from firebase_admin import firestore
from config import GUILD_IDS

ENABLE_DIRECT_REDEEM = False


class RedeemCommand(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="redeem_submit",
        description="Submit gift code / 提交兌換碼（呱呱要開功能）",
    )
    @app_commands.describe(code="禮包碼", player_id="玩家 ID(可選)")
    async def redeem_submit(
        self, interaction: discord.Interaction, code: str, player_id: str = None
    ):
        await interaction.response.defer(thinking=True)

        if len(code) < 6 or code.isdigit():
            await interaction.followup.send(
                "❌ Invalid code format. Code must be at least 6 characters and contain letters.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild_id)

        if not player_id:
            docs = (
                self.db.collection("ids")
                .document(guild_id)
                .collection("players")
                .stream()
            )
            player_ids = [doc.to_dict()["player_id"] for doc in docs]
            batch_id = str(uuid.uuid4())[:8]

            for pid in player_ids:
                task = {
                    "code": code,
                    "player_id": pid,
                    "channel_id": interaction.channel.id,
                    "status": "pending",
                    "batch_id": batch_id,
                }
                self.db.collection("redeem_tasks").add(task)

            await interaction.followup.send(
                "All players submitted. Waiting for redeem result...",
                ephemeral=True,
            )
        else:
            if not (player_id.isdigit() and len(player_id) == 9):
                await interaction.followup.send(
                    "❌ Invalid player ID. Must be 9-digit numeric ID.",
                    ephemeral=True,
                )
                return

            docs = (
                self.db.collection("ids")
                .document(guild_id)
                .collection("players")
                .where("player_id", "==", player_id)
                .stream()
            )
            found = any(True for _ in docs)

            if not found:
                self.db.collection("ids").document(guild_id).collection(
                    "players"
                ).document(player_id).set({"player_id": player_id})
                await interaction.followup.send(
                    f"📌 Player ID `{player_id}` added to Firestore.",
                    ephemeral=True,
                )

            task = {
                "code": code,
                "player_id": player_id,
                "channel_id": interaction.channel.id,
                "status": "pending",
                "batch_id": None,
            }
            self.db.collection("redeem_tasks").add(task)

            await interaction.followup.send(
                f"{player_id} -> Waiting for redeem result...",
                ephemeral=True,
            )

    async def cog_load(self):
        for gid in GUILD_IDS:
            guild = discord.Object(id=gid)
            if ENABLE_DIRECT_REDEEM:
                self.bot.tree.add_command(self.redeem, guild=guild)
            self.bot.tree.add_command(self.redeem_submit, guild=guild)


async def setup(bot):
    await bot.add_cog(RedeemCommand(bot))
