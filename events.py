import discord
import datetime
import asyncio

async def send_startup_message(bot, channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title="🚀 YUGIBOT OPÉRATIONNEL",
            description="### **UP !**\nLe système de farm et le marché sont désormais **en ligne**.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        await channel.send(embed=embed)

async def delayed_help(interaction):
    """Attend 3 secondes puis affiche l'aide après l'inscription."""
    await asyncio.sleep(3)
    # On crée une version simplifiée de l'appel help
    from bot import help_embed
    embed = help_embed()
    await interaction.followup.send(content="✨ Voici un guide pour bien débuter :", embed=embed)
