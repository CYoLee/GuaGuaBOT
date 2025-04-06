import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
import pytz
from tasks.notify_loop import run_notify_once
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [1299413864160428054, 1125331349654470786]
TIMEZONE = pytz.timezone("Asia/Taipei")

# 初始化 Firebase
cred_json = os.environ.get("FIREBASE_CREDENTIALS", "{}")
cred = credentials.Certificate(eval(cred_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ GuaGuaBOT is online as {bot.user}")

    # ⚠️ 清除全域指令
    await bot.tree.sync()  # 先拉下現有的
    bot.tree.clear_commands()  # 全部清除
    await bot.tree.sync()  # 同步上去
    print("🧹 Cleared global slash commands.")

    # ✅ 接著重新註冊 Guild 指令
    for gid in GUILD_IDS:
        guild = discord.Object(id=gid)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands for guild {gid}")

    # notify_task.start()


# ✅ 自動通知排程
@tasks.loop(seconds=30)
async def notify_task():
    await run_notify_once(bot)

    # try:
    #     docs = (
    #         db.collection("notifications")
    #         .where(filter=FieldFilter("datetime", ">=", lower_bound))
    #         .where(filter=FieldFilter("datetime", "<=", upper_bound))
    #         .stream()
    #     )

    #     for doc in docs:
    #         data = doc.to_dict()
    #         channel_id = data.get("channel_id")
    #         mention = data.get("mention", "")
    #         message = data.get("message", "")

    #         try:
    #             channel = await bot.fetch_channel(channel_id)
    #             if channel:
    #                 content = (
    #                     f"{mention}\n⏰ 活動提醒 ⏰{message}"
    #                     if mention
    #                     else f"⏰ 活動提醒 ⏰{message}"
    #                 )
    #                 await channel.send(content)
    #                 db.collection("notifications").document(doc.id).delete()
    #             else:
    #                 print(f"⚠️ 無法取得頻道：{channel_id}")
    #         except Exception as e:
    #             print(f"❌ 發送提醒失敗（頻道 {channel_id}）：{type(e).__name__}: {e}")

    # except Exception as e:
    #     print(f"❌ notify_task 整體失敗：{type(e).__name__}: {e}")


# ✅ 載入所有指令模組
async def load_cogs():
    await bot.load_extension("cogs.id_manager")
    await bot.load_extension("cogs.notify")
    await bot.load_extension("cogs.redeem_command")
    await bot.load_extension("cogs.help_command")
    await bot.load_extension("cogs.debug_notify")


async def main():
    async with bot:
        await load_cogs()
        notify_task.start()
        print("✅ notify_task loop started")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
