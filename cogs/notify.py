# cogs/notify.py
import discord
from discord import app_commands
from discord.ext.commands import Cog
from firebase_admin import firestore
from datetime import datetime
from typing import Optional
import pytz

from config import GUILD_IDS, ROLE_PERMISSIONS, LOG_CHANNEL_ID, LOG_FIRESTORE_ENABLED

TIMEZONE = pytz.timezone("Asia/Taipei")


def has_permission(interaction: discord.Interaction, command_name: str) -> bool:
    allowed_roles = ROLE_PERMISSIONS.get(command_name, [])
    return any(role.id in allowed_roles for role in interaction.user.roles)


async def send_notify_log(
    bot: discord.Client, message: str, guild_id: Optional[str] = None
):
    timestamp = datetime.now().astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    try:
        channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(f"📝 [`{timestamp}`] {message}")
    except Exception as e:
        print(f"❌ Discord log failed: {type(e).__name__}: {e}")

    if LOG_FIRESTORE_ENABLED:
        try:
            db = firestore.client()
            log_data = {
                "message": message,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "datetime": timestamp,
                "source": "notify.py",
            }
            if guild_id:
                log_data["guild_id"] = str(guild_id)
            db.collection("logs").add(log_data)
        except Exception as e:
            print(f"❌ Firestore log failed: {type(e).__name__}: {e}")


class Notify(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="add_notify", description="新增活動提醒(可多日期或多時間)"
    )
    @app_commands.describe(
        date="提醒日期 (YYYY-MM-DD, 多個用逗號分隔)",
        time="提醒時間 (HH:MM, 多個用逗號分隔)",
        message="提醒內容",
        mention="要標記的人 (可選)",
        channel="發送頻道 (可選)",
    )
    async def add_notify(
        self,
        interaction: discord.Interaction,
        date: str,
        time: str,
        message: str,
        mention: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
    ):
        await interaction.response.defer(thinking=True)

        if not has_permission(interaction, "add_notify"):
            await interaction.followup.send("🚫 你沒有權限新增提醒", ephemeral=True)
            return

        if channel:
            if not channel.permissions_for(interaction.user).send_messages:
                await interaction.followup.send(
                    "❌ 沒有權限發送到該頻道", ephemeral=True
                )
                return
        else:
            channel = interaction.channel

        dates = [d.strip() for d in date.split(",") if d.strip()]
        times = [t.strip() for t in time.split(",") if t.strip()]

        if len(dates) > 1 and len(times) > 1:
            await interaction.followup.send(
                "❌ 僅支援多日期+單時間 或 單日期+多時間", ephemeral=True
            )
            return

        total = dates if len(times) == 1 else times
        for i in total:
            try:
                dt_str = f"{i} {times[0]}" if len(times) == 1 else f"{dates[0]} {i}"
                dt = TIMEZONE.localize(datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))
            except ValueError:
                await interaction.followup.send(
                    f"❌ 時間格式錯誤：{dt_str}", ephemeral=True
                )
                return

            self.db.collection("notifications").add(
                {
                    "guild_id": str(interaction.guild_id),
                    "channel_id": channel.id,
                    "datetime": dt,
                    "mention": mention or "",
                    "message": message,
                }
            )

            await send_notify_log(
                self.bot,
                f"{interaction.user} 新增提醒 `{dt_str}` 到 <#{channel.id}> in guild {interaction.guild_id}",
                guild_id=interaction.guild_id,
            )

        await interaction.followup.send("✅ 提醒已新增", ephemeral=True)

    @app_commands.command(name="list_notify", description="查看提醒列表")
    async def list_notify(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", str(interaction.guild_id))
            .order_by("datetime")
            .stream()
        )
        docs = list(docs)
        if not docs:
            await interaction.followup.send("⚠️ 尚未設定任何提醒", ephemeral=True)
            return

        self.bot.cached_notify_docs = [(i, d.id) for i, d in enumerate(docs)]
        messages = [
            f"[{i}] {d.to_dict()['datetime'].astimezone(TIMEZONE).strftime('%Y-%m-%d %H:%M')} | {d.to_dict()['message']}"
            for i, d in enumerate(docs)
        ]
        await interaction.followup.send(
            "📅 提醒列表：\n" + "\n".join(messages), ephemeral=True
        )

    @app_commands.command(name="remove_notify", description="移除提醒 (index)")
    @app_commands.describe(index="提醒編號")
    async def remove_notify(self, interaction: discord.Interaction, index: int):
        await interaction.response.defer(thinking=True)

        if not has_permission(interaction, "remove_notify"):
            await interaction.followup.send("🚫 你沒有權限移除提醒", ephemeral=True)
            return

        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", str(interaction.guild_id))
            .order_by("datetime")
            .stream()
        )
        doc_list = list(docs)
        if index < 0 or index >= len(doc_list):
            await interaction.followup.send("❌ 無效 index", ephemeral=True)
            return

        doc_id = doc_list[index].id
        self.db.collection("notifications").document(doc_id).delete()

        await interaction.followup.send(f"🗑️ 已移除提醒 index `{index}`", ephemeral=True)
        await send_notify_log(
            self.bot,
            f"{interaction.user} 移除了提醒 index `{index}`（doc: {doc_id}）in guild {interaction.guild_id}",
            guild_id=interaction.guild_id,
        )

    @app_commands.command(name="edit_notify", description="編輯提醒內容 (by index)")
    @app_commands.describe(
        index="提醒編號",
        date="新日期(YYYY-MM-DD)",
        time="新時間(HH:MM)",
        message="新提醒內容",
        mention="新 mention (可選)",
        channel="新頻道 (可選)",
    )
    async def edit_notify(
        self,
        interaction: discord.Interaction,
        index: int,
        date: str = None,
        time: str = None,
        message: str = None,
        mention: str = None,
        channel: Optional[discord.TextChannel] = None,
    ):
        await interaction.response.defer(thinking=True)

        if not has_permission(interaction, "edit_notify"):
            await interaction.followup.send("🚫 你沒有權限編輯提醒", ephemeral=True)
            return

        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", str(interaction.guild_id))
            .order_by("datetime")
            .stream()
        )
        doc_list = list(docs)
        if index < 0 or index >= len(doc_list):
            await interaction.followup.send("❌ 無效的 index", ephemeral=True)
            return

        doc_ref = doc_list[index].reference
        old_data = doc_list[index].to_dict()
        updated = {}

        if message:
            updated["message"] = message
        if mention is not None:
            updated["mention"] = mention
        if channel:
            if not channel.permissions_for(interaction.user).send_messages:
                await interaction.followup.send("❌ 沒有權限發送到頻道", ephemeral=True)
                return
            updated["channel_id"] = channel.id
        if date or time:
            try:
                date_str = date or old_data["datetime"].strftime("%Y-%m-%d")
                time_str = time or old_data["datetime"].strftime("%H:%M")
                dt = TIMEZONE.localize(
                    datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                )
                updated["datetime"] = dt
            except ValueError:
                await interaction.followup.send("❌ 時間格式錯誤", ephemeral=True)
                return

        if not updated:
            await interaction.followup.send("⚠️ 請填寫至少一項欄位", ephemeral=True)
            return

        doc_ref.update(updated)
        await interaction.followup.send("✅ 提醒已更新", ephemeral=True)

        await send_notify_log(
            self.bot,
            f"{interaction.user} 編輯提醒 index `{index}` in guild {interaction.guild_id}，更新欄位: {list(updated.keys())}",
            guild_id=interaction.guild_id,
        )

    async def cog_load(self):
        for gid in GUILD_IDS:
            guild = discord.Object(id=gid)
            self.bot.tree.add_command(self.add_notify, guild=guild)
            self.bot.tree.add_command(self.list_notify, guild=guild)
            self.bot.tree.add_command(self.remove_notify, guild=guild)
            self.bot.tree.add_command(self.edit_notify, guild=guild)


async def setup(bot):
    await bot.add_cog(Notify(bot))
