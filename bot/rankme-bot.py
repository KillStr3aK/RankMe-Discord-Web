import os
import json

import aiomysql
import aiohttp

import discord
from discord.ext import commands
from discord.ext.commands import Bot

with open("{}/config.json".format(os.path.dirname(os.path.realpath(__file__)))) as config_file:  
    config = json.load(config_file)

with open("{}/translations.json".format(os.path.dirname(os.path.realpath(__file__)))) as translations_file:  
    translations = json.load(translations_file)

language = config["general"]["language"]

if discord.version_info.major == 1:
    client = commands.Bot(command_prefix=config["general"]["prefix"])

    @client.event
    async def on_ready():
        print(translations[language]["connection-successful"].format(client, config["general"]["community-name"], discord.__version__, "1.0.0"))

    @client.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            print(error.retry_after)
            await ctx.send(translations[language]["command-cooldown"].format(ctx.author.id, error.retry_after))
        else:
            print(error)

    @client.command()
    @commands.cooldown(1, config["general"]["command-cooldown"], commands.BucketType.user)
    async def top(ctx):
        conn = await aiomysql.connect(host=config["rankme"]["mysql"]["servername"], port=config["rankme"]["mysql"]["port"],
                                      user=config["rankme"]["mysql"]["username"], password=config["rankme"]["mysql"]["password"],
                                      db=config["rankme"]["mysql"]["dbname"])
        async with conn.cursor() as cur:
            await cur.execute("SELECT steam, name, score, kills, deaths FROM {} ORDER BY {} DESC LIMIT {}".format(config["rankme"]["table-name"], config["rankme"]["order-by"], config["rankme"]["top-limit"]))
            r = await cur.fetchall()

            embed = discord.Embed(title=translations[language]["top-message-title"].format(config["rankme"]["top-limit"]), colour=discord.Colour(0x0e9fed))
            counter = 0
            for row in r:
                counter += 1
                embed.add_field(name="{}. {}".format(counter, row[1][:15]), value=translations[language]["top-message"].format(row[2], row[3], row[4], row[0]), inline=True)

            await ctx.send(embed=embed)

            await cur.close()
        
        conn.close()

    @client.command()
    @commands.cooldown(1, config["general"]["command-cooldown"], commands.BucketType.user)
    async def rank(ctx, steamid = None):
        if steamid:
            conn = await aiomysql.connect(host=config["rankme"]["mysql"]["servername"], port=config["rankme"]["mysql"]["port"],
                                          user=config["rankme"]["mysql"]["username"], password=config["rankme"]["mysql"]["password"],
                                          db=config["rankme"]["mysql"]["dbname"])
            session_object = aiohttp.ClientSession()
            async with session_object as session:
                async with session.get("https://api.steamid.uk/convert.php?api={}&input={}&format=json".format(config["rankme"]["steamid-uk-api-key"], steamid)) as r:
                    if r.status == 200:
                        steam = await r.json()
                        if steam["query_time"]["results"] == "0":
                            await ctx.send(translations[language]["incorrect-steam-id"].format(ctx.author.id))
                        else:
                            if "STEAM_0" in steam["converted"]["steamid"]:
                                steamid32 = steam["converted"]["steamid"].replace("STEAM_0", "STEAM_1")
                            else:
                                steamid32 = steam["converted"]["steamid"]
                            
                            async with conn.cursor() as cur:
                                await cur.execute("SELECT steam, name, score, kills, deaths, assists, shots, hits, headshots, rounds_tr, rounds_ct, lastconnect, damage FROM {} WHERE steam='{}' LIMIT 1".format(config["rankme"]["table-name"], steamid32))
                                if cur.rowcount != 0:
                                    r = await cur.fetchall()

                                    rounds_played = r[0][9] + r[0][10]

                                    if r[0][3] > 0 and r[0][4] > 0:
                                        kdr = round(r[0][3] / r[0][4], 2)
                                        hsp = round((r[0][8] / r[0][3])*100, 0)
                                    else:
                                        kdr = 0
                                        hsp = 0

                                    if rounds_played > 0 and r[0][12] > 0:
                                        adr = round(r[0][12] / rounds_played, 2)
                                    else:
                                        adr = 0
                                    
                                    kills = r[0][3]
                                    deaths = r[0][4]
                                    assists = r[0][5]
                                    headshots = r[0][8]
                                else:
                                    rounds_played = 0
                                    kdr = 0
                                    hsp = 0
                                    adr = 0
                                    kills = 0
                                    deaths = 0
                                    assists = 0
                                    headshots = 0

                                steamapi_session_object = aiohttp.ClientSession()
                                async with steamapi_session_object as steam_session:
                                    async with steam_session.get("http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={}&steamids={}".format(config["rankme"]["steam-api-key"], steam["converted"]["steamid64"])) as r_steam:
                                        if r_steam.status == 200:
                                            steam_api = await r_steam.json()

                                            embed = discord.Embed(title="{}'s Profile".format(steam_api["response"]["players"][0]["personaname"]), colour=discord.Colour(0x0e9fed), url=config["rankme"]["stats-page-url"].format(steamid32))
                                            embed.set_thumbnail(url=steam_api["response"]["players"][0]["avatarfull"])

                                            embed.add_field(name=translations[language]["kills"], value=kills, inline=True)
                                            embed.add_field(name=translations[language]["deaths"], value=deaths, inline=True)
                                            embed.add_field(name=translations[language]["assists"], value=assists, inline=True)
                                            embed.add_field(name=translations[language]["headshots"], value=headshots, inline=True)
                                            embed.add_field(name=translations[language]["kdr"], value=kdr, inline=True)
                                            embed.add_field(name=translations[language]["hs-percentage"], value="{}%".format(hsp), inline=True)
                                            embed.add_field(name=translations[language]["rounds-played"], value=rounds_played, inline=True)
                                            embed.add_field(name=translations[language]["adr"], value=adr, inline=True)

                                            await ctx.send(embed=embed)

                                steamapi_session_object.close
                                await cur.close()
                                
            session_object.close
            conn.close()
        else:
            await ctx.send(translations[language]["rank-command-incorrect-format"].format(ctx.author.id, config["general"]["prefix"]))

    client.run(config["general"]["bot-token"])
else:
    print(translations[language]["wrong-version"].format(discord.__version__))
