import discord
import datetime

async def send_startup_message(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title="🚀 YUGIBOT OPÉRATIONNEL",
            description="### **UP !**\nLe système de farm et le marché sont désormais **en ligne**.\n\nPréparez vos jetons, le farm commence maintenant !",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text="Railway Cloud Deployment")
        await channel.send(embed=embed)
