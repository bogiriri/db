import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import random
import os
from database import init_db, get_connection
from events import send_startup_message, delayed_help

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_CHANNEL_ID = 1223265970580357232

def help_embed():
    """Génère l'embed d'aide pour /help et /in."""
    embed = discord.Embed(title="📖 GUIDE DU DUELLISTE DE JETONS", color=discord.Color.blue())
    embed.description = (
        "### 🚜 Mécanique de Farm\n"
        "Lancez `/farm` pour commencer à générer votre jeton personnel. "
        "Tant que vous farmez, les autres commandes sont bloquées (sauf si vous avez le **Droïde**).\n\n"
        "### 💰 Économie (Daily)\n"
        "Le `/daily` de base rapporte entre **50 et 100 Ƶ** toutes les **24h**.\n"
        "Le farm rapporte aussi un bonus de **50-100 Ƶ toutes les 2h** de travail.\n\n"
        "### 📈 Le Marché (/jeton)\n"
        "La valeur des jetons change toutes les **3h**.\n"
        "- **+5%** si personne ne le farme.\n"
        "- **-5%** si plus d'un joueur le farme.\n\n"
        "### 🏛️ Le Temple\n"
        "Achetez des trophées pour réduire le cooldown du daily ou farmer en arrière-plan."
    )
    return embed

class GameBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.first_run = True 

    async def setup_hook(self):
        init_db()
        await self.tree.sync()
        self.market_cycle.start()

    async def on_ready(self):
        if self.first_run:
            await send_startup_message(self, ALLOWED_CHANNEL_ID)
            self.first_run = False

    @tasks.loop(hours=3)
    async def market_cycle(self):
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
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Salon autorisé : <#{ALLOWED_CHANNEL_ID}>", ephemeral=True)
        return False
    return True

# --- COMMANDES ---

@bot.tree.command(name="help", description="Détails des commandes et mécaniques")
async def help_cmd(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    await interaction.response.send_message(embed=help_embed())

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
    
    await interaction.response.send_message(f"### ✅ BIENVENUE {name.upper()}\nInitialisation de ton compte...")
    # Lancement de l'aide automatique après 3 secondes
    await delayed_help(interaction)

@bot.tree.command(name="daily", description="Gagner des Zanzibars")
async def daily(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_farming, has_droid, last_daily, daily_cooldown_hours, daily_min, daily_max FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()
    if not p: return await interaction.response.send_message("Fais `/in`.", ephemeral=True)
    if p[0] and not p[1]: return await interaction.response.send_message("🚫 Occupé à farmer !", ephemeral=True)

    now = datetime.datetime.now()
    if p[2] and (now - p[2]).total_seconds() < p[3] * 3600:
        diff = datetime.timedelta(seconds=int(p[3]*3600 - (now - p[2]).total_seconds()))
        return await interaction.response.send_message(f"⏳ Reviens dans **{diff.seconds//3600}h et {(diff.seconds//60)%60}min**.")

    gain = random.randint(p[4], p[5])
    cursor.execute("UPDATE Players SET zanzibar = zanzibar + %s, last_daily = %s WHERE id_discord = %s", (gain, now, interaction.user.id))
    conn.commit()
    await interaction.response.send_message(f"### 💰 +{gain} Zanzibars !")

@bot.tree.command(name="farm", description="Lancer/Arrêter le farm")
async def farm(interaction: discord.Interaction):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_farming, start_farm_time, prod_multiplier FROM Players WHERE id_discord = %s", (interaction.user.id,))
    p = cursor.fetchone()

    if not p[0]:
        cursor.execute("UPDATE Players SET is_farming = True, start_farm_time = %s WHERE id_discord = %s", (datetime.datetime.now(), interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers + 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message("🚜 **Farm lancé !**")
    else:
        now = datetime.datetime.now()
        hours = (now - p[1]).total_seconds() / 3600
        token_gain = round(hours * p[2], 2)
        money_bonus = (int(hours) // 2) * random.randint(50, 100)
        cursor.execute("UPDATE Inventory SET amount = amount + %s WHERE player_id = %s", (token_gain, interaction.user.id))
        cursor.execute("UPDATE Players SET is_farming = False, zanzibar = zanzibar + %s WHERE id_discord = %s", (money_bonus, interaction.user.id))
        cursor.execute("UPDATE Tokens SET total_farmers = total_farmers - 1 WHERE token_name IN (SELECT token_name FROM Inventory WHERE player_id = %s)", (interaction.user.id,))
        await interaction.response.send_message(f"### 🛑 FIN DU FARM\nGain : **{token_gain}** jetons et **{money_bonus} Ƶ**.")
    conn.commit()

@bot.tree.command(name="jeton", description="Le Marché")
async def jeton(interaction: discord.Interaction, numero_achat: int = None):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT token_name, current_value FROM Tokens")
    tokens = cursor.fetchall()

    if numero_achat is None:
        embed = discord.Embed(title="🏮 MARCHÉ DU CASINO", color=0xcc0000)
        embed.description = "\n".join([f"**{i+1}. {t[0].upper()}** : `{round(t[1], 1)} Ƶ`" for i, t in enumerate(tokens)])
        return await interaction.response.send_message(embed=embed)

    target = tokens[numero_achat-1]
    cursor.execute("UPDATE Inventory SET token_name = %s WHERE player_id = %s", (target[0], interaction.user.id)) # Simplifié
    await interaction.response.send_message(f"✅ Tu possèdes maintenant le jeton de {target[0]} !")
    conn.commit()

@bot.tree.command(name="filou", description="Magouilles du Filou")
async def filou(interaction: discord.Interaction, numero_action: int = None):
    if not await check_channel(interaction): return
    conn = get_connection()
    cursor = conn.cursor()
    
    actions = [
        ("Krach Boursier", "Vend les jetons de TOUS les joueurs contre du Zanzibar."),
        ("Le Switch", "Échange ton jeton contre celui d'un joueur aléatoire.")
    ]

    if numero_action is None:
        embed = discord.Embed(title="🃏 REPAIRE DU FILOU", color=0x000000) # Cadre NOIR
        embed.description = "\n".join([f"**{i+1}. {a[0]}**\n┕ {a[1]}" for i, a in enumerate(actions)])
        return await interaction.response.send_message(embed=embed)

    if numero_action == 1: # KRACH : Vente totale
        cursor.execute("""
            UPDATE Players p SET zanzibar = zanzibar + (
                SELECT COALESCE(SUM(i.amount * t.current_value), 0)
                FROM Inventory i JOIN Tokens t ON i.token_name = t.token_name
                WHERE i.player_id = p.id_discord
            )
        """)
        cursor.execute("UPDATE Inventory SET amount = 0")
        await interaction.response.send_message("💥 **KRACH !** Tout le monde a été forcé de vendre ses stocks !")
    
    elif numero_action == 2: # SWITCH : Échange aléatoire
        cursor.execute("SELECT token_name FROM Tokens ORDER BY RANDOM() LIMIT 1")
        new_token = cursor.fetchone()[0]
        cursor.execute("UPDATE Inventory SET token_name = %s WHERE player_id = %s", (new_token, interaction.user.id))
        await interaction.response.send_message(f"🔄 **SWITCH !** Tes jetons ont été transformés en **{new_token}** !")

    conn.commit()
    cursor.close()
    conn.close()

bot.run(TOKEN)
