# cogs/debug_notify.py
import discord
from discord import app_commands
from discord.ext.commands import Cog
from config import GUILD_IDS
from tasks.notify_loop import run_notify_once
from firebase_admin import firestore
from datetime import datetime
import pytz

OWNER_ID = 271962747225374721  # ✅ 你的 Discord ID
TIMEZONE = pytz.timezone("Asia/Taipei")


class DebugNotify(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="trigger_notify_test", description="立即執行通知排程（手動測試）"
    )
    async def trigger_notify_test(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "🚫 你無權使用這個指令。", ephemeral=True
            )
            return

        await interaction.response.send_message("🛠️ 立即執行通知排程...", ephemeral=True)
        await run_notify_once(self.bot)

    @app_commands.command(name="show_now_time", description="顯示 BOT 現在時間")
    async def show_now_time(self, interaction: discord.Interaction):
        now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        await interaction.response.send_message(
            f"⏰ 現在 BOT 時間：`{now}`（Asia/Taipei）", ephemeral=True
        )

    @app_commands.command(name="whoami", description="查看你的 Discord 使用者資訊")
    async def whoami(self, interaction: discord.Interaction):
        user = interaction.user
        roles = [role.name for role in user.roles if role.name != "@everyone"]
        role_list = ", ".join(roles) if roles else "None"
        await interaction.response.send_message(
            f"👤 你的名稱：`{user.name}#{user.discriminator}`\n"
            f"🆔 你的 ID：`{user.id}`\n"
            f"🪪 身分組：{role_list}",
            ephemeral=True,
        )

    @app_commands.command(name="debug_firestore_count", description="顯示提醒總筆數")
    async def debug_firestore_count(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", guild_id)
            .stream()
        )
        count = sum(1 for _ in docs)
        await interaction.response.send_message(
            f"📊 Firestore 中提醒總筆數：`{count}`", ephemeral=True
        )

    async def cog_load(self):
        for gid in GUILD_IDS:
            guild = discord.Object(id=gid)
            self.bot.tree.add_command(self.trigger_notify_test, guild=guild)
            self.bot.tree.add_command(self.show_now_time, guild=guild)
            self.bot.tree.add_command(self.whoami, guild=guild)
            self.bot.tree.add_command(self.debug_firestore_count, guild=guild)

            print(f"✅ cog_load() triggered in debug_notify for guild: {gid}")

        # ✅ 強制刷新一次指令（防止未同步成功）
        # synced = await self.bot.tree.sync(guild=guild)
        # print(f"🔁 Synced {len(synced)} command(s) to guild: {gid}")


async def setup(bot):
    await bot.add_cog(DebugNotify(bot))
