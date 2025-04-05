# cogs/help_command.py
import discord
from discord import app_commands
from discord.ext.commands import Cog

GUILD_IDS = [1299413864160428054, 1125331349654470786]


class HelpCommand(Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help message / 顯示說明")
    @app_commands.describe(language="Choose language (zh or en)")
    @app_commands.choices(
        language=[
            app_commands.Choice(name="繁體中文", value="zh"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def help(
        self, interaction: discord.Interaction, language: app_commands.Choice[str]
    ):
        if language.value == "en":
            content = (
                "**GuaGuaBOT Command List (English):**\n\n"
                "• `/redeem_submit` - Submit gift code\n"
                "• `/add_id` - Add a player ID\n"
                "• `/remove_id` - Remove a player ID\n"
                "• `/list_ids` - List all saved player IDs\n"
                "• `/add_notify` - Add event reminder\n"
                "• `/remove_notify` - Remove event reminder\n"
                "• `/list_notify` - List all reminders\n"
            )
        else:
            content = (
                "**GuaGuaBOT 指令列表（繁體中文）：**\n\n"
                "• `/redeem_submit` - 呱呱要開機才能兌換\n"
                "• `/add_id` - 新增玩家ID - 下次組隊兌換\n"
                "• `/remove_id` - 移除玩家ID - 不要給我亂移除\n"
                "• `/list_ids` - 列出所有玩家ID - 看看誰是幸運兒\n"
                "• `/add_notify` - 新增活動提醒 - 可以指定標記\n"
                "• `/remove_notify` - 移除活動提醒 - 打錯也不擔心\n"
                "• `/list_notify` - 查看目前提醒列表 - 但你看不到誰要吵你\n"
            )
        await interaction.response.send_message(content, ephemeral=True)

    # async def cog_load(self):
    #     for gid in GUILD_IDS:
    #         self.bot.tree.add_command(self.help, guild=discord.Object(id=gid))


async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
