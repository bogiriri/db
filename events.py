import discord
import datetime
import asyncio

async def send_startup_message(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title="🚀 YUGIBOT OPÉRATIONNEL",
            description="### **UP !**\nLe système est en ligne.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        await channel.send(embed=embed)

def get_help_embed():
    embed = discord.Embed(title="📖 GUIDE DU JOUEUR", color=discord.Color.blue())
    embed.add_field(name="🚜 /farm", value="Lance ou arrête la production de jetons.", inline=False)
    embed.add_field(name="💰 /daily", value="Récupère tes Zanzibars (50-100 base).", inline=False)
    embed.add_field(name="📈 /jeton", value="Marché en temps réel.", inline=False)
    embed.add_field(name="🏛️ /temple", value="Boutique de trophées.", inline=False)
    return embed

async def delayed_help(interaction):
    await asyncio.sleep(3)
    await interaction.followup.send(content="✨ Voici le guide :", embed=get_help_embed())
