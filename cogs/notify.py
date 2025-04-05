import discord
from discord import app_commands
from discord.ext.commands import Cog
from firebase_admin import firestore
from datetime import datetime
import pytz

GUILD_IDS = [1299413864160428054, 1125331349654470786]
TIMEZONE = pytz.timezone("Asia/Taipei")


class Notify(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="add_notify", description="Add event reminder / 新增活動提醒"
    )
    @app_commands.describe(
        date="提醒日期（可用逗號分隔，如：2025-04-05,2025-04-06）",
        time="提醒時間（可用逗號分隔，如：20:30,21:00）",
        message="提醒內容",
        mention="要標記的人（可選）",
    )
    async def add_notify(
        self,
        interaction: discord.Interaction,
        date: str,
        time: str,
        message: str,
        mention: str = None,
    ):
        await interaction.response.defer(thinking=True)

        dates = [d.strip() for d in date.split(",") if d.strip()]
        times = [t.strip() for t in time.split(",") if t.strip()]

        # 🚫 禁止同時輸入多個日期與多個時間
        if len(dates) > 1 and len(times) > 1:
            await interaction.followup.send(
                "❌ 不支援同時輸入多個日期與多個時間，請擇一使用多筆輸入。",
                ephemeral=True,
            )
            return

        added_count = 0

        for d in dates:
            for t in times:
                try:
                    dt_str = f"{d} {t}"
                    naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    aware_dt = TIMEZONE.localize(naive_dt)
                except ValueError:
                    await interaction.followup.send(
                        f"❌ 時間格式錯誤：`{d}` + `{t}`，請使用 YYYY-MM-DD 與 HH:MM。",
                        ephemeral=True,
                    )
                    return

                data = {
                    "guild_id": str(interaction.guild_id),
                    "channel_id": interaction.channel.id,
                    "datetime": aware_dt,
                    "mention": mention or "",
                    "message": message,
                }

                self.db.collection("notifications").add(data)
                added_count += 1

        await interaction.followup.send(f"✅ 已新增 {added_count} 筆提醒。")

    @app_commands.command(
        name="list_notify", description="List all reminders / 查看目前提醒列表"
    )
    async def list_notify(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", guild_id)
            .order_by("datetime")
            .stream()
        )

        messages = []
        for doc in docs:
            data = doc.to_dict()
            dt = data["datetime"].astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            messages.append(f"- {dt} | {data['message']}")

        if messages:
            await interaction.followup.send("📅 提醒列表：\n" + "\n".join(messages))
        else:
            await interaction.followup.send("⚠️ 尚未設定任何提醒。")

    @app_commands.command(
        name="remove_notify", description="Remove event reminder / 移除活動提醒"
    )
    @app_commands.describe(message="輸入欲刪除的提醒內容關鍵字")
    async def remove_notify(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(thinking=True)

        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", guild_id)
            .stream()
        )

        deleted = 0
        for doc in docs:
            data = doc.to_dict()
            if message in data.get("message", ""):
                self.db.collection("notifications").document(doc.id).delete()
                deleted += 1

        if deleted:
            await interaction.followup.send(f"🗑️ 已移除 {deleted} 筆提醒。")
        else:
            await interaction.followup.send("❌ 找不到符合條件的提醒。")

    async def cog_load(self):
        for gid in GUILD_IDS:
            guild = discord.Object(id=gid)
            self.bot.tree.add_command(self.add_notify, guild=guild)
            self.bot.tree.add_command(self.list_notify, guild=guild)
            self.bot.tree.add_command(self.remove_notify, guild=guild)


async def setup(bot):
    await bot.add_cog(Notify(bot))
