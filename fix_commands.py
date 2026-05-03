"""Nuclear fix: clear everything, re-register globally AND per-guild, wait for propagation"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
import os

with open('config.json') as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot: {bot.user}')
    print(f'Guilds: {[g.name for g in bot.guilds]}')

    # Step 1: Clear EVERYTHING
    print('\n=== STEP 1: CLEARING ALL COMMANDS ===')
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    print('Global cleared')

    for guild in bot.guilds:
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f'{guild.name} cleared')

    print('Waiting 5 seconds...')
    await asyncio.sleep(5)

    # Step 2: Load the game commands cog
    print('\n=== STEP 2: LOADING COGS ===')
    try:
        from wallet_system import WalletSystem
        from stats_tracker import StatsTracker
        from wager_tracker import WagerTracker

        wallet = WalletSystem()
        stats = StatsTracker()
        wager = WagerTracker()
        cooldowns = {}

        class DummyHistory:
            def next_id(self): return 1
            def add_result(self, *a): pass
            def format_history(self, *a): return "No games yet"

        class DummyLogger:
            async def log_game(self, *a): pass

        import game_commands
        await game_commands.setup(bot, config, wallet, wager, stats, cooldowns, DummyHistory(), DummyLogger())
        print('Cog loaded')
    except Exception as e:
        print(f'Cog error: {e}')
        import traceback
        traceback.print_exc()

    # Step 3: Sync to each guild
    print('\n=== STEP 3: SYNCING COMMANDS ===')
    all_cmds = bot.tree.get_commands()
    print(f'Commands in tree: {len(all_cmds)}')
    for c in all_cmds:
        print(f'  /{c.name}')

    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f'\nSynced {len(synced)} to {guild.name}:')
        for c in synced:
            print(f'  /{c.name} (ID: {c.id})')

    # Also sync globally as backup
    print('\n=== STEP 4: GLOBAL SYNC ===')
    global_synced = await bot.tree.sync()
    print(f'Synced {len(global_synced)} globally')

    print('\n=== DONE ===')
    print('Commands are registered both globally and per-guild.')
    print('Global commands can take up to 1 hour to appear.')
    print('Guild commands should be instant.')
    await bot.close()

bot.run(config['bot_token'])
