import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import random
import os
from database import init_db, get_connection

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_CHANNEL_ID = 1223265970580357232

# Initialisation des tables au lancement
init_db()

class GameBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        self.market_cycle.start()
        print(f"Bot connecté en tant que {self.user}")

    @tasks.loop(hours=3)
    async def market_cycle(self):
        conn = get_connection()
        cursor = conn.cursor()
        # Logique de prix : -10% si farmé, +10% si délaissé
        cursor.execute("UPDATE Tokens SET current_value = current_value * 1.10 WHERE total_farmers = 0")
        cursor.execute("UPDATE Tokens SET current_value = current_value * 0.90 WHERE total_farmers > 1")
        conn.commit()
        cursor.close()
        conn.close()

bot = GameBot()

# --- MIDDLEWARE : VERIFICATION DU SALON ---
async def check_channel(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Les commandes de jeu ne sont autorisées que dans le salon <#{ALLOWED_CHANNEL_ID}>.", 
            ephemeral=True
        )
        return False
    return True

# --- COMMANDES ---

@bot.tree.command(name="in", description="S'inscrire au jeu")
async def sign_in(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    
    conn = get_connection()
    cursor = conn.cursor()
    user_id = interaction.user.id
    name = interaction.user.name.replace(" ", "_")

    cursor.execute("SELECT id_discord FROM Players WHERE id_discord = %s", (user_id,))
    if cursor.fetchone():
        return await interaction.response.send_message("Tu es déjà inscrit !", ephemeral=True)

    cursor.execute("INSERT INTO Players (id_discord, name) VALUES (%s, %s)", (user_id, name))
    cursor.execute("INSERT INTO Tokens (token_name) VALUES (%s)", (name,))
    cursor.execute("INSERT INTO Inventory (player_id, token_name) VALUES (%s, %s)", (user_id, name))
    
    conn.commit()
    cursor.close()
    conn.close()
    await interaction.response.send_message(f"✅ Bienvenue **{name}** ! Ton jeton personnel est maintenant sur le marché.")

@bot.tree.command(name="farm", description="Lancer ou arrêter ton farm")
async def farm(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_farming, start_farm_time, prod_multiplier FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()

    if not p: return await interaction.response.send_message("Fais `/in` pour commencer.")

    if not p[0]: # DEBUT DU FARM
        cursor.execute("UPDATE Players SET is_farming = True, start_farm_time = %s WHERE id_discord = %s", (datetime.datetime.now(), interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers + 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message("🚜 Tu viens de partir farmer tes jetons. Les commandes actives sont bloquées !")
    else: # FIN DU FARM
        now = datetime.datetime.now()
        hours = (now - p[1]).total_seconds() / 3600
        token_gain = round(hours * p[2], 2)
        money_bonus = (int(hours) // 2) * random.randint(50, 100)
        
        cursor.execute("UPDATE Inventory SET amount = amount + %s WHERE player_id = %s", (token_gain, interaction.user.id))
        cursor.execute("UPDATE Players SET is_farming = False, zanzibar = zanzibar + %s WHERE id_discord = %s", (money_bonus, interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers - 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message(f"🛑 Fin du farm !\n💰 Bonus : **{money_bonus} Ƶ**\n🪙 Jetons gagnés (par type possédé) : **{token_gain}**")
    
    conn.commit()
    cursor.close()
    conn.close()

@bot.tree.command(name="me", description="Voir tes stats et jetons")
async def me(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT zanzibar, name, is_farming FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Utilise `/in` d'abord.")

    cursor.execute("SELECT token_name, amount FROM Inventory WHERE player_id = %s", (interaction.user.id,))
    inv = cursor.fetchall()
    
    txt = "\n".join([f"• **{i[0]}** : {round(i[1], 2)}" for i in inv])
    embed = discord.Embed(title=f"Profil de {p[1]}", color=discord.Color.green())
    embed.add_field(name="Zanzibar", value=f"{p[0]} Ƶ", inline=True)
    embed.add_field(name="Statut", value="🚜 Farming" if p[2] else "💤 Repos", inline=True)
    embed.add_field(name="Tes Jetons", value=txt if txt else "Aucun", inline=False)
    
    await interaction.response.send_message(embed=embed)
    cursor.close()
    conn.close()

# Lancement du bot
bot.run(TOKEN)
