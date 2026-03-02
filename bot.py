import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime, random, os
from database import init_db, get_connection
from events import send_startup_message, get_help_embed, delayed_help
from market import update_market_prices

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

    async def on_ready(self):
        if self.first_run:
            await send_startup_message(self, ALLOWED_CHANNEL_ID)
            self.first_run = False

    @tasks.loop(hours=3)
    async def market_cycle(self):
        conn = get_connection()
        update_market_prices(conn.cursor())
        conn.commit()
        conn.close()

bot = GameBot()

# --- COMMANDES ---

@bot.tree.command(name="help")
async def h(it: discord.Interaction):
    if it.channel_id != ALLOWED_CHANNEL_ID: return
    await it.response.send_message(embed=get_help_embed())

@bot.tree.command(name="in")
async def signup(it: discord.Interaction):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id_discord FROM Players WHERE id_discord = %s", (it.user.id,))
    if cur.fetchone(): return await it.response.send_message("Déjà inscrit !")
    
    name = it.user.name.replace(" ", "_")
    cur.execute("INSERT INTO Players (id_discord, name) VALUES (%s, %s)", (it.user.id, name))
    cur.execute("INSERT INTO Tokens (token_name) VALUES (%s)", (name,))
    cur.execute("INSERT INTO Inventory (player_id, token_name) VALUES (%s, %s)", (it.user.id, name))
    conn.commit(); conn.close()
    await it.response.send_message(f"✅ Bienvenue {name} ! Ton compte est créé.")
    await delayed_help(it)

@bot.tree.command(name="me")
async def profile(it: discord.Interaction):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT zanzibar, is_farming, name FROM Players WHERE id_discord = %s", (it.user.id,))
    p = cur.fetchone()
    if not p: return await it.response.send_message("Fais /in")
    
    cur.execute("SELECT token_name, amount FROM Inventory WHERE player_id = %s", (it.user.id,))
    inv = cur.fetchall()
    embed = discord.Embed(title=f"PROFIL DE {p[2].upper()}", color=0x2ecc71)
    embed.add_field(name="Zanzibar", value=f"{p[0]} Ƶ")
    embed.add_field(name="Statut", value="🚜 Farming" if p[1] else "💤 Repos")
    txt = "\n".join([f"• {i[0]} : {round(i[1], 2)}" for i in inv])
    embed.add_field(name="Inventaire", value=txt or "Vide", inline=False)
    await it.response.send_message(embed=embed)
    conn.close()

@bot.tree.command(name="farm")
async def farm_cmd(it: discord.Interaction):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT is_farming, start_farm_time, prod_multiplier FROM Players WHERE id_discord = %s", (it.user.id,))
    p = cur.fetchone()
    if not p[0]:
        cur.execute("UPDATE Players SET is_farming = True, start_farm_time = %s WHERE id_discord = %s", (datetime.datetime.now(), it.user.id))
        await it.response.send_message("🚜 Farm lancé !")
    else:
        hours = (datetime.datetime.now() - p[1]).total_seconds() / 3600
        gain = round(hours * p[2], 2)
        cur.execute("UPDATE Inventory SET amount = amount + %s WHERE player_id = %s", (gain, it.user.id))
        cur.execute("UPDATE Players SET is_farming = False WHERE id_discord = %s", (it.user.id,))
        await it.response.send_message(f"🛑 Stop ! Gain : {gain} jetons.")
    conn.commit(); conn.close()

@bot.tree.command(name="daily")
async def daily_cmd(it: discord.Interaction):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT last_daily, daily_cooldown_hours, daily_min, daily_max, is_farming, has_droid FROM Players WHERE id_discord = %s", (it.user.id,))
    p = cur.fetchone()
    if p[4] and not p[5]: return await it.response.send_message("🚫 Occupé !")
    
    now = datetime.datetime.now()
    if p[0] and (now - p[0]).total_seconds() < p[1] * 3600:
        return await it.response.send_message("⏳ Pas encore !")
        
    gain = random.randint(p[2], p[3])
    cur.execute("UPDATE Players SET zanzibar = zanzibar + %s, last_daily = %s WHERE id_discord = %s", (gain, now, it.user.id))
    conn.commit(); conn.close()
    await it.response.send_message(f"💰 +{gain} Zanzibars !")

@bot.tree.command(name="jeton")
async def market_cmd(it: discord.Interaction, numero: int = None):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT token_name, current_value FROM Tokens")
    tkns = cur.fetchall()
    if numero is None:
        e = discord.Embed(title="🏮 MARCHÉ", color=0xcc0000)
        e.description = "\n".join([f"{i+1}. {t[0]} : {round(t[1], 1)} Ƶ" for i, t in enumerate(tkns)])
        return await it.response.send_message(embed=e)
    # Logique achat... (simplifiée)
    await it.response.send_message(f"✅ Jeton {numero} sélectionné.")

@bot.tree.command(name="filou")
async def filou_cmd(it: discord.Interaction, numero: int = None):
    if numero is None:
        e = discord.Embed(title="🃏 FILOU", color=0x000000)
        e.description = "1. Krach (Vente forcée)\n2. Switch (Token aléatoire)"
        return await it.response.send_message(embed=e)
    
    conn = get_connection(); cur = conn.cursor()
    if numero == 1: # KRACH
        cur.execute("UPDATE Players SET zanzibar = zanzibar + 100") # Exemple
        cur.execute("UPDATE Inventory SET amount = 0")
        await it.response.send_message("💥 KRACH !")
    elif numero == 2: # SWITCH
        cur.execute("SELECT token_name FROM Tokens ORDER BY RANDOM() LIMIT 1")
        nt = cur.fetchone()[0]
        cur.execute("UPDATE Inventory SET token_name = %s WHERE player_id = %s", (nt, it.user.id))
        await it.response.send_message(f"🔄 Switch vers {nt} !")
    conn.commit(); conn.close()

bot.run(TOKEN)
