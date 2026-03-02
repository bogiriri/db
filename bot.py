import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import random
import os
from database import init_db, get_connection
from events import send_startup_message

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_CHANNEL_ID = 1223265970580357232

class GameBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.first_run = True 

    async def setup_hook(self):
        init_db()
        await self.tree.sync()
        self.market_cycle.start()
        print(f"✅ Bot connecté : {self.user}")

    async def on_ready(self):
        if self.first_run:
            await send_startup_message(self, ALLOWED_CHANNEL_ID)
            self.first_run = False

    @tasks.loop(hours=3)
    async def market_cycle(self):
        """Mise à jour automatique du marché toutes les 3h"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Tokens SET current_value = current_value * 1.05 WHERE total_farmers = 0")
        cursor.execute("UPDATE Tokens SET current_value = current_value * 0.95 WHERE total_farmers > 1")
        conn.commit()
        cursor.close()
        conn.close()

bot = GameBot()

# --- HELPERS ---
async def check_channel(interaction: discord.Interaction):
    """Vérifie si la commande est lancée dans le bon salon"""
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(f"❌ Salon autorisé : <#{ALLOWED_CHANNEL_ID}>", ephemeral=True)
        return False
    return True

async def can_act(interaction: discord.Interaction, cursor):
    """Vérifie si le joueur est occupé à farmer"""
    cursor.execute("SELECT is_farming, has_droid FROM Players WHERE id_discord = %s", (interaction.user.id,))
    res = cursor.fetchone()
    if res and res[0] and not res[1]:
        await interaction.response.send_message("🚫 Tu es en plein farm ! (Achète le Droïde au /temple)", ephemeral=True)
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
    await interaction.response.send_message(f"### ✅ BIENVENUE {name.upper()}\nTon jeton personnel a été injecté sur le marché !")

@bot.tree.command(name="daily", description="Gagner des Zanzibars")
async def daily(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    if not await can_act(interaction, cursor): return

    cursor.execute("SELECT last_daily, daily_cooldown_hours, daily_min, daily_max FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Fais /in d'abord.")

    now = datetime.datetime.now()
    if p[0] and (now - p[0]).total_seconds() < p[1] * 3600:
        diff = datetime.timedelta(seconds=int(p[1]*3600 - (now - p[0]).total_seconds()))
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return await interaction.response.send_message(f"⏳ **Reviens dans {hours}h et {minutes}min !**")

    gain = random.randint(p[2], p[3])
    cursor.execute("UPDATE Players SET zanzibar = zanzibar + %s, last_daily = %s WHERE id_discord = %s", (gain, now, interaction.user.id))
    conn.commit()
    await interaction.response.send_message(f"### 💰 DAILY RÉCUPÉRÉ\nTu as gagné **{gain} Zanzibars** !")

@bot.tree.command(name="farm", description="Lancer ou arrêter ton farm")
async def farm(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_farming, start_farm_time, prod_multiplier FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()

    if not p[0]: # START
        cursor.execute("UPDATE Players SET is_farming = True, start_farm_time = %s WHERE id_discord = %s", (datetime.datetime.now(), interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers + 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message("🚜 **Tu pars au champ !** Tes jetons se génèrent...")
    else: # STOP
        now = datetime.datetime.now()
        hours = (now - p[1]).total_seconds() / 3600
        token_gain = round(hours * p[2], 2)
        money_bonus = (int(hours) // 2) * random.randint(50, 100)
        
        cursor.execute("UPDATE Inventory SET amount = amount + %s WHERE player_id = %s", (token_gain, interaction.user.id))
        cursor.execute("UPDATE Players SET is_farming = False, zanzibar = zanzibar + %s WHERE id_discord = %s", (money_bonus, interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers - 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message(f"### 🛑 FIN DU FARM\nGain : **{token_gain}** jetons (par type) et **{money_bonus} Ƶ**.")
    
    conn.commit()
    cursor.close()
    conn.close()

@bot.tree.command(name="me", description="Voir ton profil")
async def me(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT zanzibar, name, is_farming FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Inscris-toi d'abord.")

    cursor.execute("SELECT token_name, amount FROM Inventory WHERE player_id = %s", (interaction.user.id,))
    inv = cursor.fetchall()
    
    embed = discord.Embed(title=f"PROFIL DE {p[1].upper()}", color=0x2ecc71)
    embed.add_field(name="Zanzibar", value=f"**{p[0]} Ƶ**", inline=True)
    embed.add_field(name="Statut", value="🚜 Farming" if p[2] else "💤 Repos", inline=True)
    
    txt = "\n".join([f"• **{i[0]}** : {round(i[1], 2)}" for i in inv])
    embed.add_field(name="Tes Jetons", value=txt if txt else "Aucun", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="jeton", description="Le Marché des Actions")
async def jeton(interaction: discord.Interaction, numero_achat: int = None):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT token_name, current_value, total_farmers FROM Tokens")
    tokens = cursor.fetchall()

    if numero_achat is None:
        embed = discord.Embed(title="🏮 MARCHÉ DU CASINO", color=0xcc0000, description="Plus un jeton est farmé, plus son prix chute !\n\n")
        for i, t in enumerate(tokens):
            embed.description += f"**{i+1}. {t[0].upper()}**\n┕ Valeur : `{round(t[1], 1)} Ƶ` | 🚜 : {t[2]}\n\n"
        embed.set_footer(text="Tape /jeton [numéro] pour acheter un droit de farm")
        return await interaction.response.send_message(embed=embed)

    # Logique d'achat par numéro
    try:
        target = tokens[numero_achat-1]
        cursor.execute("SELECT zanzibar, has_trader_1 FROM Players WHERE id_discord = %s", (interaction.user.id,))
        p = cursor.fetchone()
        
        if not p[1]: return await interaction.response.send_message("🔒 Trophée Trader I requis.", ephemeral=True)
        if p[0] < target[1]: return await interaction.response.send_message("❌ Pas assez de Zanzibars.")

        cursor.execute("INSERT INTO Inventory (player_id, token_name) VALUES (%s, %s) ON CONFLICT DO NOTHING", (interaction.user.id, target[0]))
        cursor.execute("UPDATE Players SET zanzibar = zanzibar - %s WHERE id_discord = %s", (target[1], interaction.user.id))
        conn.commit()
        await interaction.response.send_message(f"✅ Tu peux maintenant farmer le jeton de **{target[0]}** !")
    except IndexError:
        await interaction.response.send_message("❌ Numéro invalide.")

@bot.tree.command(name="temple", description="Boutique des Trophées")
async def temple(interaction: discord.Interaction, numero_item: int = None):
    if not await check_channel(interaction): return
    items = [
        ("Trophée Double", "Daily toutes les 12h", 10000),
        ("Trophée Money I", "Daily passe à 75-200", 5000),
        ("Trophée Droïde", "Actif pendant le farm", 25000),
        ("Trophée Trader I", "Acheter des jetons tiers", 100)
    ]

    if numero_item is None:
        embed = discord.Embed(title="🏛️ LE TEMPLE DES DIEUX", color=0xf1c40f)
        for i, it in enumerate(items):
            embed.description = embed.description or ""
            embed.description += f"### {i+1}. {it[0]}\n*{it[1]}*\n┕ Prix : **{it[2]} Ƶ**\n\n"
        return await interaction.response.send_message(embed=embed)

    # Logique d'achat (simplifiée pour l'exemple)
    await interaction.response.send_message(f"🛒 Vérification du stock pour l'item **{numero_item}**...")

@bot.tree.command(name="top", description="Classement Mondial")
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
    
    embed = discord.Embed(title="🏆 CLASSEMENT DES FORTUNES", color=0xf1c40f)
    res = ""
    for i, r in enumerate(rows):
        res += f"## {i+1}. {r[0].upper()}\n┕ Fortune : **{round(r[1], 1)} Ƶ-Value**\n\n"
    embed.description = res
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="filou", description="Magouilles")
async def filou(interaction: discord.Interaction, numero_action: int = None):
    if not await check_channel(interaction): return
    actions = [
        ("Krach Boursier", "Reset la valeur des jetons à 100"),
        ("Reset Marché", "Force tout le monde à vendre ses jetons tiers")
    ]

    if numero_action is None:
        embed = discord.Embed(title="🃏 REPAIRE DU FILOU", color=0x2c3e50)
        desc = ""
        for i, a in enumerate(actions):
            desc += f"**{i+1}. {a[0]}**\n┕ {a[1]}\n\n"
        embed.description = desc
        return await interaction.response.send_message(embed=embed)

    await interaction.response.send_message(f"🎭 **Le Filou lance l'action {numero_action}...**")

bot.run(TOKEN)
