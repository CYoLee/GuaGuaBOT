# bot.py
import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio
from datetime import timedelta
import pytz
from tasks.notify_loop import run_notify_once
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_IDS = [1299413864160428054, 1125331349654470786]
TIMEZONE = pytz.timezone("Asia/Taipei")

cred_json = os.environ.get("FIREBASE_CREDENTIALS", "{}")
cred = credentials.Certificate(eval(cred_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ GuaGuaBOT is online as {bot.user}")

    await bot.tree.sync()
    bot.tree.clear_commands()
    await bot.tree.sync()
    print("🧹 Cleared global slash commands.")

    for gid in GUILD_IDS:
        guild = discord.Object(id=gid)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands for guild {gid}")


@tasks.loop(seconds=30)
async def notify_task():
    await run_notify_once(bot)


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
