import discord
import datetime

async def send_startup_message(bot, channel_id):
    """Envoie un message stylé quand le bot est en ligne."""
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title="🚀 Système Opérationnel",
            description="**UP !** Le bot est en ligne et prêt pour le farm.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text="Railway Deployment Success")
        await channel.send(embed=embed)
        print(f"✅ Message 'UP !' envoyé dans le salon {channel_id}")
