import discord
from discord import app_commands
from discord.ext.commands import Cog
from firebase_admin import firestore
from config import GUILD_IDS  # 引用 GUILD_IDS


class IDManager(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="add_id", description="Add a player ID (9 digits) / 新增玩家ID(9位數)"
    )
    @app_commands.describe(player_id="Player ID (9 digits)")
    async def add_id(self, interaction: discord.Interaction, player_id: str):
        if not player_id.isdigit() or len(player_id) != 9:
            await interaction.response.send_message(
                "❌ Invalid player ID format. Please enter a 9-digit number.",
                ephemeral=True,
            )
            return
        guild_id = str(interaction.guild_id)  # Fetch the guild ID
        existing = (
            self.db.collection("ids")
            .document(guild_id)
            .collection("players")
            .where("player_id", "==", player_id)
            .stream()
        )
        if any(existing):
            await interaction.response.send_message(
                f"⚠️ Player ID `{player_id}` already exists.", ephemeral=True
            )
            return

        self.db.collection("ids").document(guild_id).collection("players").add(
            {"player_id": player_id}
        )
        await interaction.response.send_message(
            f"✅ Player ID `{player_id}` added successfully.", ephemeral=True
        )

    @app_commands.command(
        name="remove_id", description="Remove a player ID / 移除玩家ID"
    )
    @app_commands.describe(player_id="Player ID to remove")
    async def remove_id(self, interaction: discord.Interaction, player_id: str):
        guild_id = str(interaction.guild_id)
        found = False
        docs = (
            self.db.collection("ids")
            .document(guild_id)
            .collection("players")
            .where("player_id", "==", player_id)
            .stream()
        )
        for doc in docs:
            self.db.collection("ids").document(guild_id).collection("players").document(
                doc.id
            ).delete()
            found = True

        if found:
            await interaction.response.send_message(
                f"🗑️ Player ID `{player_id}` removed successfully.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ Player ID `{player_id}` not found.", ephemeral=True
            )

    @app_commands.command(
        name="list_ids", description="List all player IDs stored / 列出所有玩家ID"
    )
    async def list_ids(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("ids").document(guild_id).collection("players").stream()
        )

        if not docs:
            await interaction.response.send_message(
                "📭 No player IDs found.", ephemeral=True
            )
            return

        ids = [doc.to_dict()["player_id"] for doc in docs]
        ids_text = "\n".join(f"- `{pid}`" for pid in ids)
        await interaction.response.send_message(
            f"📋 Player ID List:\n{ids_text}", ephemeral=True
        )

    async def cog_load(self):
        for gid in GUILD_IDS:  # Use GUILD_IDS defined in config.py or another location
            guild = discord.Object(id=gid)
            self.bot.tree.add_command(self.add_id, guild=guild)
            self.bot.tree.add_command(self.remove_id, guild=guild)
            self.bot.tree.add_command(self.list_ids, guild=guild)


async def setup(bot):
    await bot.add_cog(IDManager(bot))
