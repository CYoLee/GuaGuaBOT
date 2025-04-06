# cogs/notify.py
import discord
from discord import app_commands
from discord.ext.commands import Cog
from firebase_admin import firestore
from datetime import datetime
import pytz
import os

from config import GUILD_IDS, ROLE_PERMISSIONS, LOG_CHANNEL_ID

TIMEZONE = pytz.timezone("Asia/Taipei")


def has_permission(interaction: discord.Interaction, command_name: str) -> bool:
    allowed_roles = ROLE_PERMISSIONS.get(command_name, [])
    return any(role.id in allowed_roles for role in interaction.user.roles)


async def send_notify_log(bot: discord.Client, message: str):
    try:
        channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if channel:
            timestamp = (
                datetime.now().astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
            )
            await channel.send(f"📝 [`{timestamp}`] {message}")
    except Exception as e:
        print(f"❌ Failed to send notify log: {type(e).__name__}: {e}")


class Notify(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = firestore.client()

    @app_commands.command(
        name="add_notify", description="新增活動提醒（可多日期或多時間）"
    )
    @app_commands.describe(
        date="提醒日期（可多個，以逗號分隔）格式：YYYY-MM-DD",
        time="提醒時間（可多個，以逗號分隔）格式：HH:MM",
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

        if not has_permission(interaction, "add_notify"):
            await interaction.followup.send("🚫 你沒有權限新增提醒。", ephemeral=True)
            return

        dates = [d.strip() for d in date.split(",") if d.strip()]
        times = [t.strip() for t in time.split(",") if t.strip()]

        if len(dates) > 1 and len(times) > 1:
            await interaction.followup.send(
                "❌ 僅允許「多個日期 + 單一時間」或「單一日期 + 多個時間」。",
                ephemeral=True,
            )
            return

        total = dates if len(times) == 1 else times
        for i in total:
            try:
                dt_str = f"{i} {times[0]}" if len(times) == 1 else f"{dates[0]} {i}"
                naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                aware_dt = TIMEZONE.localize(naive_dt)
            except ValueError:
                await interaction.followup.send(
                    f"❌ 時間格式錯誤：{dt_str}，請使用 YYYY-MM-DD 與 HH:MM。",
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

        await interaction.followup.send("✅ 提醒已新增。")

    @app_commands.command(
        name="list_notify", description="查看目前提醒列表（含 index）"
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
        indexed_docs = []
        for i, doc in enumerate(docs):
            data = doc.to_dict()
            dt = data["datetime"].astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M")
            messages.append(f"[{i}] {dt} | {data['message']}")
            indexed_docs.append((i, doc.id))

        if messages:
            await interaction.followup.send(
                "📅 提醒列表（請記住 index 編號）：\n" + "\n".join(messages),
                ephemeral=True,
            )
            self.bot.cached_notify_docs = indexed_docs
        else:
            await interaction.followup.send("⚠️ 尚未設定任何提醒。", ephemeral=True)

    @app_commands.command(
        name="remove_notify", description="移除活動提醒（使用 index）"
    )
    @app_commands.describe(index="提醒列表中的編號")
    async def remove_notify(self, interaction: discord.Interaction, index: int):
        await interaction.response.defer(thinking=True)

        if not has_permission(interaction, "remove_notify"):
            await interaction.followup.send("🚫 你沒有權限移除提醒。", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", guild_id)
            .order_by("datetime")
            .stream()
        )
        doc_list = list(docs)

        if index < 0 or index >= len(doc_list):
            await interaction.followup.send("❌ 無效的 index 編號。", ephemeral=True)
            return

        doc_id = doc_list[index].id
        self.db.collection("notifications").document(doc_id).delete()
        await interaction.followup.send(
            f"🗑️ 已成功移除 index `{index}` 的提醒。", ephemeral=True
        )

        username = f"{interaction.user.name}#{interaction.user.discriminator}"
        user_id = interaction.user.id
        await send_notify_log(
            self.bot,
            f"{username} ({user_id}) 移除了提醒 index `{index}`（doc ID: {doc_id}） in guild {interaction.guild_id}",
        )

    @app_commands.command(
        name="edit_notify", description="編輯提醒內容（依 index 修改）"
    )
    @app_commands.describe(
        index="提醒列表中的編號",
        date="新的日期（格式：YYYY-MM-DD）",
        time="新的時間（格式：HH:MM）",
        message="新的提醒內容",
        mention="新的 mention（可選）",
    )
    async def edit_notify(
        self,
        interaction: discord.Interaction,
        index: int,
        date: str = None,
        time: str = None,
        message: str = None,
        mention: str = None,
    ):
        await interaction.response.defer(thinking=True)

        if not has_permission(interaction, "edit_notify"):
            await interaction.followup.send("🚫 你沒有權限編輯提醒。", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        docs = (
            self.db.collection("notifications")
            .where("guild_id", "==", guild_id)
            .order_by("datetime")
            .stream()
        )
        doc_list = list(docs)

        if index < 0 or index >= len(doc_list):
            await interaction.followup.send("❌ 無效的 index 編號。", ephemeral=True)
            return

        doc_ref = doc_list[index].reference
        old_data = doc_list[index].to_dict()

        updated_data = {}

        if message:
            updated_data["message"] = message
        if mention is not None:
            updated_data["mention"] = mention

        if date or time:
            try:
                date_str = date if date else old_data["datetime"].strftime("%Y-%m-%d")
                time_str = time if time else old_data["datetime"].strftime("%H:%M")
                dt_str = f"{date_str} {time_str}"
                naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                updated_data["datetime"] = TIMEZONE.localize(naive_dt)
            except ValueError:
                await interaction.followup.send(
                    "❌ 新的時間格式錯誤，請使用 YYYY-MM-DD 與 HH:MM。", ephemeral=True
                )
                return

        if not updated_data:
            await interaction.followup.send(
                "⚠️ 請至少填寫一個要修改的欄位。", ephemeral=True
            )
            return

        doc_ref.update(updated_data)
        await interaction.followup.send("✅ 提醒已成功更新。", ephemeral=True)

        username = f"{interaction.user.name}#{interaction.user.discriminator}"
        user_id = interaction.user.id
        await send_notify_log(
            self.bot,
            f"{username} ({user_id}) 編輯提醒 index `{index}` in guild {interaction.guild_id}，欄位更新: {list(updated_data.keys())}",
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
