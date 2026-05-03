"""
Final fix: clear ALL duplicates, then start the bot properly
"""
import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
import requests

TOKEN = json.load(open('config.json'))['bot_token']
APP_ID = '1448714382304477306'
HEADERS = {'Authorization': f'Bot {TOKEN}'}

def clear_via_api():
    """Use REST API to nuke every single command"""
    # Clear global
    r = requests.put(
        f'https://discord.com/api/v10/applications/{APP_ID}/commands',
        headers=HEADERS, json=[]
    )
    print(f'Global clear: {r.status_code}')

    # Get guilds
    r = requests.get('https://discord.com/api/v10/users/@me/guilds', headers=HEADERS)
    guilds = r.json()

    for g in guilds:
        r = requests.put(
            f'https://discord.com/api/v10/applications/{APP_ID}/guilds/{g["id"]}/commands',
            headers=HEADERS, json=[]
        )
        print(f'{g["name"]} clear: {r.status_code}')

if __name__ == '__main__':
    print('=== NUKING ALL COMMANDS VIA API ===')
    clear_via_api()

    print('\nWaiting 5 seconds...')
    import time
    time.sleep(5)

    # Verify
    r = requests.get(f'https://discord.com/api/v10/applications/{APP_ID}/commands', headers=HEADERS)
    print(f'\nGlobal commands remaining: {len(r.json())}')

    r = requests.get('https://discord.com/api/v10/users/@me/guilds', headers=HEADERS)
    for g in r.json():
        r2 = requests.get(f'https://discord.com/api/v10/applications/{APP_ID}/guilds/{g["id"]}/commands', headers=HEADERS)
        print(f'{g["name"]} commands remaining: {len(r2.json())}')

    print('\nDONE - all commands nuked. Now starting bot.py for fresh sync...')
