"""Clear ALL discord commands (global + guild) then exit"""
import discord
import json

with open('config.json') as f:
    config = json.load(f)

bot = discord.Client(intents=discord.Intents.default())
tree = discord.app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    # Clear global commands
    print('Clearing global commands...')
    tree.clear_commands(guild=None)
    await tree.sync()
    print('Global commands cleared!')

    # Clear each guild
    for guild in bot.guilds:
        print(f'Clearing commands for {guild.name}...')
        tree.clear_commands(guild=guild)
        await tree.sync(guild=guild)
        print(f'{guild.name} cleared!')

    print('DONE - All commands cleared. Now restart bot.py to resync fresh.')
    await bot.close()

bot.run(config['bot_token'])
