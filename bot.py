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

class GameBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        init_db()  # Initialisation des tables SQL
        await self.tree.sync() # Synchronisation forcée des commandes Slash
        self.market_cycle.start() # Lance l'actualisation du marché toutes les 3h
        print(f"✅ Bot connecté : {self.user} | Commandes synchronisées.")

    @tasks.loop(hours=3)
    async def market_cycle(self):
        """Mise à jour du marché : Prix monte si délaissé, baisse si trop farmé"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Tokens SET current_value = current_value * 1.05 WHERE total_farmers = 0")
        cursor.execute("UPDATE Tokens SET current_value = current_value * 0.95 WHERE total_farmers > 1")
        conn.commit()
        cursor.close()
        conn.close()

bot = GameBot()

# --- UTILS / MIDDLEWARES ---

async def check_channel(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(f"❌ Utilise le salon <#{ALLOWED_CHANNEL_ID}> !", ephemeral=True)
        return False
    return True

async def can_act(interaction: discord.Interaction, cursor):
    """Vérifie si le joueur peut faire une commande active (Farm + Droïde)"""
    cursor.execute("SELECT is_farming, has_droid FROM Players WHERE id_discord = %s", (interaction.user.id,))
    res = cursor.fetchone()
    if res and res[0] and not res[1]:
        await interaction.response.send_message("🚫 Tu farmes actuellement ! (Achète le Droïde au /temple)", ephemeral=True)
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
        return await interaction.response.send_message("Déjà inscrit !", ephemeral=True)

    cursor.execute("INSERT INTO Players (id_discord, name) VALUES (%s, %s)", (user_id, name))
    cursor.execute("INSERT INTO Tokens (token_name) VALUES (%s)", (name,))
    cursor.execute("INSERT INTO Inventory (player_id, token_name) VALUES (%s, %s)", (user_id, name))
    conn.commit()
    cursor.close()
    conn.close()
    await interaction.response.send_message(f"✅ Bienvenue **{name}** ! Ton jeton est sur le marché.")

@bot.tree.command(name="daily", description="Gagner des Zanzibars")
async def daily(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    if not await can_act(interaction, cursor): return

    cursor.execute("SELECT last_daily, daily_cooldown_hours, daily_min, daily_max FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Fais /in", ephemeral=True)

    now = datetime.datetime.now()
    if p[0] and (now - p[0]).total_seconds() < p[1] * 3600:
        minutes = int((p[1] * 3600 - (now - p[0]).total_seconds()) // 60)
        return await interaction.response.send_message(f"⏳ Reviens dans {minutes} min.", ephemeral=True)

    gain = random.randint(p[2], p[3])
    cursor.execute("UPDATE Players SET zanzibar = zanzibar + %s, last_daily = %s WHERE id_discord = %s", (gain, now, interaction.user.id))
    conn.commit()
    await interaction.response.send_message(f"💰 +{gain} Zanzibars !")

@bot.tree.command(name="farm", description="Lancer/Arrêter le farm")
async def farm(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_farming, start_farm_time, prod_multiplier FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()

    if not p[0]: # START
        cursor.execute("UPDATE Players SET is_farming = True, start_farm_time = %s WHERE id_discord = %s", (datetime.datetime.now(), interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers + 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message("🚜 Farm lancé !")
    else: # STOP
        now = datetime.datetime.now()
        hours = (now - p[1]).total_seconds() / 3600
        token_gain = round(hours * p[2], 2)
        money_bonus = (int(hours) // 2) * random.randint(50, 100)
        
        cursor.execute("UPDATE Inventory SET amount = amount + %s WHERE player_id = %s", (token_gain, interaction.user.id))
        cursor.execute("UPDATE Players SET is_farming = False, zanzibar = zanzibar + %s WHERE id_discord = %s", (money_bonus, interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers - 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message(f"🛑 Fin. Gain: {token_gain} jetons et {money_bonus} Ƶ.")
    conn.commit()

@bot.tree.command(name="me", description="Ton profil")
async def me(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT zanzibar, name, is_farming FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Fais /in")

    cursor.execute("SELECT token_name, amount FROM Inventory WHERE player_id = %s", (interaction.user.id,))
    inv = cursor.fetchall()
    txt = "\n".join([f"• **{i[0]}** : {round(i[1], 2)}" for i in inv])
    
    embed = discord.Embed(title=f"Profil de {p[1]}", color=0x00ff00)
    embed.add_field(name="Argent", value=f"{p[0]} Ƶ")
    embed.add_field(name="Inventaire", value=txt if txt else "Vide", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="top", description="Classement par valeur")
async def top(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.name, SUM(i.amount * t.current_value) as val 
        FROM Players p JOIN Inventory i ON p.id_discord = i.player_id 
        JOIN Tokens t ON i.token_name = t.token_name 
        GROUP BY p.name ORDER BY val DESC LIMIT 10
    """)
    rows = cursor.fetchall()
    res = "\n".join([f"{i+1}. **{r[0]}** : {round(r[1], 1)} pts" for i, r in enumerate(rows)])
    await interaction.response.send_message(f"🏆 **LEADERBOARD (Valeur Marchande)** :\n{res}")

@bot.tree.command(name="jeton", description="Marché des jetons (Achat/Vente)")
async def jeton(interaction: discord.Interaction, acheter_nom: str = None, vendre_nom: str = None):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    user_id = interaction.user.id

    if not acheter_nom and not vendre_nom:
        cursor.execute("SELECT token_name, current_value, total_farmers FROM Tokens")
        all_t = cursor.fetchall()
        txt = "\n".join([f"**{t[0]}** : {round(t[1], 1)} Ƶ ({t[2]} farmers)" for t in all_t])
        return await interaction.response.send_message(f"📈 **MARCHÉ**\n{txt}")

    cursor.execute("SELECT has_trader_1, has_trader_2, zanzibar, name FROM Players WHERE id_discord = %s", (user_id,))
    p = cursor.fetchone()

    if acheter_nom:
        if not p[0]: return await interaction.response.send_message("🔒 Trophée Trader I requis.", ephemeral=True)
        cursor.execute("SELECT current_value FROM Tokens WHERE token_name = %s", (acheter_nom,))
        val = cursor.fetchone()
        if val and p[2] >= val[0]:
            cursor.execute("INSERT INTO Inventory (player_id, token_name) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, acheter_nom))
            cursor.execute("UPDATE Players SET zanzibar = zanzibar - %s WHERE id_discord = %s", (val[0], user_id))
            await interaction.response.send_message(f"✅ Tu peux farmer le jeton de **{acheter_nom}** !")
        else:
            await interaction.response.send_message("❌ Impossible d'acheter.")

    if vendre_nom:
        if not p[1]: return await interaction.response.send_message("🔒 Trophée Trader II requis.", ephemeral=True)
        cursor.execute("DELETE FROM Inventory WHERE player_id = %s AND token_name = %s", (user_id, vendre_nom))
        await interaction.response.send_message(f"📤 Tu ne farmes plus le jeton de **{vendre_nom}**.")
    
    conn.commit()

@bot.tree.command(name="temple", description="Acheter des trophées")
@app_commands.choices(item=[
    app_commands.Choice(name="Trophée Double (10k Ƶ) - Daily 12h", value="double"),
    app_commands.Choice(name="Trophée Money I (5k Ƶ) - Boost Daily", value="money1"),
    app_commands.Choice(name="Trophée Money II (10k Ƶ) - Super Boost", value="money2"),
    app_commands.Choice(name="Trophée Droïde (25k Ƶ) - Farm Passif", value="droid"),
    app_commands.Choice(name="Trophée Joueur I (5k Ƶ + 1k jetons) - Prod x2", value="joueur1"),
    app_commands.Choice(name="Trophée Trader I (100 jetons) - Acheter jetons", value="trader1")
])
async def temple(interaction: discord.Interaction, item: app_commands.Choice[str]):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    if not await can_act(interaction, cursor): return
    
    user_id = interaction.user.id
    cursor.execute("SELECT zanzibar, daily_min, has_trader_1 FROM Players WHERE id_discord = %s", (user_id,))
    p = cursor.fetchone()
    
    msg = "❌ Conditions non remplies."
    
    if item.value == "double" and p[0] >= 10000:
        cursor.execute("UPDATE Players SET zanzibar = zanzibar - 10000, daily_cooldown_hours = 12 WHERE id_discord = %s", (user_id,))
        msg = "🏆 Trophée Double acquis ! Daily toutes les 12h."
    elif item.value == "money1" and p[0] >= 5000:
        cursor.execute("UPDATE Players SET zanzibar = zanzibar - 5000, daily_min = 75, daily_max = 200 WHERE id_discord = %s", (user_id,))
        msg = "🏆 Money I acquis !"
    elif item.value == "droid" and p[0] >= 25000:
        cursor.execute("UPDATE Players SET zanzibar = zanzibar - 25000, has_droid = True WHERE id_discord = %s", (user_id,))
        msg = "🤖 Droïde acquis ! Tu peux agir pendant le farm."
    elif item.value == "trader1" and p[0] >= 100: # Exemple simplifié
        cursor.execute("UPDATE Players SET has_trader_1 = True, zanzibar = zanzibar - 100 WHERE id_discord = %s", (user_id,))
        msg = "📈 Trader I acquis !"

    conn.commit()
    await interaction.response.send_message(msg)

@bot.tree.command(name="filou", description="Magouilles")
async def filou(interaction: discord.Interaction, action: str):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    if action == "reset":
        cursor.execute("UPDATE Tokens SET current_value = 100")
        cursor.execute("DELETE FROM Inventory WHERE token_name != (SELECT name FROM Players WHERE id_discord = Inventory.player_id)")
        await interaction.response.send_message("🃏 **KRACH !** Le marché repart à zéro.")
    conn.commit()

bot.run(TOKEN)
