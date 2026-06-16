import discord
from discord.ext import tasks
import requests
import asyncio

# ==================== CONFIGURATION (METS TES TOKENS ICI) ====================
DISCORD_TOKEN = "MTUxNjQxMjY0Mjg3NTQwODQwNQ.GeLHj1.7UsBErQSmqMHjnjNDZO6EYW-9zTNAo40QfHobc"
BRAWL_API_KEY =  "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6Ijg0YTA2MzI1LTEyMGYtNDE3Ni04YjllLTRmZjYxYjkwYmJhZiIsImlhdCI6MTc3OTMxNDg0OSwic3ViIjoiZGV2ZWxvcGVyL2I0MTFiZmY1LWZhNWEtOTcxNS1iNWFlLWU0ODViY2Q1YzFjMSIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiOTIuMTM4LjEyOC4xMzIiXSwidHlwZSI6ImNsaWVudCJ9XX0.gnIeoOIPOFUsM5I0Wrsps8YiHqzV48yCg3YDfR-Pk-W1GtusO219iWzFhTTT2lrxy5fNxTya1-qLSb-dv0lyaw"
# ============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

headers = {"Authorization": f"Bearer {BRAWL_API_KEY}", "Accept": "application/json"}

# Ce dictionnaire stocke les joueurs surveillés.
# Structure : { "TAG": {"channel_id": ID_SALON, "last_time": DERNIER_MATCH} }
tracked_players = {}

def parse_battle(battle, player_tag):
    """Parse les données de la partie pour Discord"""
    battle_info = battle.get("battle", {})
    mode = battle_info.get("mode", "Inconnu").capitalize()
    map_id = battle_info.get("locationId", "Inconnue")
    
    embed = discord.Embed(title="🚨 Partie Terminée !", color=discord.Color.blue())
    embed.add_field(name="🎮 Mode", value=mode, inline=True)
    embed.add_field(name="📍 Map ID", value=str(map_id), inline=True)

    if "teams" in battle_info:
        for i, team in enumerate(battle_info["teams"]):
            text = ""
            for p in team:
                star = "⭐ " if p.get("tag") == player_tag else ""
                brawler = p.get("brawler", {})
                text += f"{star}**{p.get('name')}** (`{p.get('tag')}`)\n└ {brawler.get('name')} ({brawler.get('trophies')} 🏆)\n\n"
            embed.add_field(name=f"👥 Équipe {i+1}", value=text, inline=False)
    elif "players" in battle_info:
        text = ""
        for p in battle_info["players"]:
            star = "⭐ " if p.get("tag") == player_tag else ""
            brawler = p.get("brawler", {})
            text += f"{star}**{p.get('name')}** - {brawler.get('name')} ({brawler.get('trophies')} 🏆)\n"
        embed.add_field(name="🤠 Joueurs", value=text, inline=False)
    return embed

@tasks.loop(seconds=15)
async def check_all_players():
    """Boucle qui vérifie tous les joueurs enregistrés dans le dictionnaire"""
    if not tracked_players:
        return

    for player_tag, info in list(tracked_players.items()):
        # L'API utilise %23 au lieu du #
        api_tag = player_tag.replace("#", "%23")
        url = f"https://api.brawlstars.com/v1/players/{api_tag}/battlelog"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                battles = response.json().get("items", [])
                if battles:
                    current_time = battles[0].get("battleTime")
                    
                    # Si c'est le premier check, on enregistre l'heure actuelle
                    if info["last_time"] is None:
                        tracked_players[player_tag]["last_time"] = current_time
                    
                    # Si l'heure a changé, nouvelle partie détectée !
                    elif current_time != info["last_time"]:
                        tracked_players[player_tag]["last_time"] = current_time
                        channel = bot.get_channel(info["channel_id"])
                        if channel:
                            embed = parse_battle(battles[0], player_tag)
                            await channel.send(embed=embed)
            else:
                print(f"[-] Erreur API Brawl Stars pour {player_tag}: {response.status_code}")
        except Exception as e:
            print(f"[-] Erreur de connexion pour {player_tag}: {e}")

@bot.event
async def on_message(message):
    # Évite que le bot se réponde à lui-même
    if message.author == bot.user:
        return

    # Commande pour lancer le suivi : .track #XXXXXX
    if message.content.startswith(".track"):
        args = message.content.split()
        if len(args) < 2:
            await message.channel.send("❌ Tu dois mettre un tag ! Exemple : `.track #9PJ9Q9L`")
            return
        
        player_tag = args[1].upper()
        
        if player_tag in tracked_players:
            await message.channel.send(f"⚠️ Le joueur `{player_tag}` est déjà surveillé ici.")
        else:
            tracked_players[player_tag] = {
                "channel_id": message.channel.id,
                "last_time": None
            }
            await message.channel.send(f"✅ Surveillance activée pour `{player_tag}` ! Les parties s'afficheront dans ce salon.")

    # Commande pour arrêter le suivi : .stoptrack #XXXXXX
    if message.content.startswith(".stoptrack"):
        args = message.content.split()
        if len(args) < 2:
            await message.channel.send("❌ Tu dois mettre un tag ! Exemple : `.stoptrack #9PJ9Q9L`")
            return
            
        player_tag = args[1].upper()
        
        if player_tag in tracked_players:
            del tracked_players[player_tag]
            await message.channel.send(f"🛑 Surveillance arrêtée pour `{player_tag}`.")
        else:
            await message.channel.send(f"❌ Le joueur `{player_tag}` n'était pas surveillé.")

@bot.event
async def on_ready():
    print(f"[+] Bot Discord connecté en tant que {bot.user}")
    check_all_players.start()

bot.run(DISCORD_TOKEN)
