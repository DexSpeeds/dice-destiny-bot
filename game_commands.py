"""
Game Slash Commands - All games as /commands for multiplayer
"""
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import os

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')

from orb_renderer import render_orb, render_orb_gif
from x99_renderer import render_99x_gif
from card_renderer import render_blackjack_hand, _cut_cards as preload_cards
from roulette_renderer import render_roulette_gif

from games.coinflip import Coinflip
from games.blackjack import Blackjack
from games.flowerpoker import FlowerPoker
from games.dice import Dice
from games.hotcold import HotCold
from games.caskets import Caskets
from games.roulette import Roulette
from games.mines import Mines
from games.ninetynine import NinetyNine
from games.diceduel import DiceDuel

# Colors
COLOR_WIN = 0x2ECC71
COLOR_LOSS = 0xE74C3C
COLOR_GOLD = 0xFFD700
COLOR_PUSH = 0x95A5A6

# Flower emoji helpers (same as bot.py)
FLOWER_EMOJI_NAMES = {
    'red': 'Red_flowers', 'blue': 'Blue_flowers', 'yellow': 'Yellow_flowers',
    'orange': 'Orange_flowers', 'purple': 'Purple_flowers', 'mixed': 'Mixed_flowers',
    'white': 'White_flowers', 'black': 'Black_flowers', 'assorted': 'Assorted_flowers',
}
FLOWER_FALLBACKS = {
    'red': '🔴', 'blue': '🔵', 'yellow': '🟡', 'orange': '🟠',
    'purple': '🟣', 'mixed': '🌈', 'white': '⚪', 'black': '⚫', 'assorted': '🎨',
}
CASKET_EMOJI_NAMES = {'coin': 'Coins_250', 'gem': 'Uncut_ruby', 'rare': 'Cosmic_talisman'}
CASKET_FALLBACKS = {'coin': '🪙', 'gem': '💎', 'rare': '👑'}

_emoji_cache = {}


def get_emoji(guild, name):
    if name in _emoji_cache:
        return _emoji_cache[name]
    if guild:
        emoji = discord.utils.get(guild.emojis, name=name)
        if emoji:
            _emoji_cache[name] = str(emoji)
            return str(emoji)
    return None


def flower_emoji(guild, color):
    name = FLOWER_EMOJI_NAMES.get(color)
    if name:
        custom = get_emoji(guild, name)
        if custom:
            return custom
    return FLOWER_FALLBACKS.get(color, '🌸')


def casket_emoji(guild, tier):
    name = CASKET_EMOJI_NAMES.get(tier)
    if name:
        custom = get_emoji(guild, name)
        if custom:
            return custom
    return CASKET_FALLBACKS.get(tier, '📦')


def parse_bet(bet_string):
    bet_string = str(bet_string).upper().strip().replace(',', '').replace(' ', '')
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
    for suffix, mult in multipliers.items():
        if bet_string.endswith(suffix):
            try:
                return int(float(bet_string[:-1]) * mult)
            except Exception:
                return 0
    try:
        return int(float(bet_string))
    except Exception:
        return 0


class ResultButtons(discord.ui.View):
    """Verify Fairness + Repeat Bet"""
    def __init__(self, seeds):
        super().__init__(timeout=300)
        self.seeds = seeds

    @discord.ui.button(label="Verify Fairness", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def verify(self, interaction, button):
        embed = discord.Embed(title="Provably Fair Verification", color=COLOR_GOLD)
        embed.add_field(name="Server Seed", value=f"`{self.seeds.get('server_seed', 'N/A')}`", inline=False)
        embed.add_field(name="Server Seed Hash", value=f"`{self.seeds.get('server_seed_hash', 'N/A')}`", inline=False)
        embed.add_field(name="Client Seed", value=f"`{self.seeds.get('client_seed', 'N/A')}`", inline=False)
        embed.add_field(name="Nonce", value=f"`{self.seeds.get('nonce', 'N/A')}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GameCommands(commands.Cog):
    """All game slash commands"""

    def __init__(self, bot, config, wallet, wager_tracker, stats, cooldowns, history, game_logger):
        self.bot = bot
        self.config = config
        self.wallet = wallet
        self.wager_tracker = wager_tracker
        self.stats = stats
        self.cooldowns = cooldowns
        self.history = history
        self.game_logger = game_logger
        self.active_mines = {}

        # Pre-load card images so blackjack doesn't timeout
        preload_cards()

        # Initialize games
        gs = config['game_settings']
        self.games = {
            'coinflip': Coinflip(payout=gs['coinflip']['payout']),
            'blackjack': Blackjack(win_payout=gs['blackjack']['win_payout'], blackjack_payout=gs['blackjack']['blackjack_payout']),
            'dice': Dice(house_edge=gs['dice']['house_edge']),
            'hotcold': HotCold(),
            'caskets': Caskets(coin_payout=gs['caskets']['coin_payout'], gem_payout=gs['caskets']['gem_payout'], rare_payout=gs['caskets']['rare_payout']),
            'flowerpoker': FlowerPoker(player_payout=gs['flowerpoker']['player_payout'], host_payout=gs['flowerpoker']['host_payout']),
            'roulette': Roulette(),
            'mines': None,  # Created per game
            'ninetynine': NinetyNine(),
            'diceduel': DiceDuel(payout=1.9),
        }

    def _check_channel(self, interaction, game_name):
        """Check if command is used in the correct game channel"""
        channels = self.config['channels'].get('game_channels', {})
        # Find the channel ID for this game
        correct_channel_id = None
        for ch_id, gname in channels.items():
            if gname == game_name:
                correct_channel_id = int(ch_id)
                break
        if correct_channel_id and interaction.channel_id != correct_channel_id:
            return f"Use this command in <#{correct_channel_id}>!"
        return None

    def _check_bet(self, user_id, game_name, bet_str, interaction=None):
        """Validate channel + bet, return (amount, error_msg)"""
        if interaction:
            ch_err = self._check_channel(interaction, game_name)
            if ch_err:
                return 0, ch_err
        amount = parse_bet(bet_str)
        if amount <= 0:
            return 0, f"Invalid bet: `{bet_str}`. Use: 100k, 1m, 5m"
        gs = self.config['game_settings'].get(game_name, {})
        mn, mx = gs.get('min_bet', 100000), gs.get('max_bet', 5000000)
        if amount < mn:
            return 0, f"Min bet: {mn:,} GP"
        if amount > mx:
            return 0, f"Max bet: {mx:,} GP"
        if not self.wallet.has_balance(user_id, amount):
            bal = self.wallet.get_balance(user_id)
            return 0, f"Insufficient balance! Have: {bal:,} GP, Need: {amount:,} GP"
        return amount, None

    def _deduct(self, user_id, game_name, amount):
        self.wallet.remove_balance(user_id, amount)
        self.wager_tracker.record_wager(user_id, amount)

        # Referral earnings - 10% of house edge to referrer
        try:
            from referral_system import ReferralSystem
            import json, os
            ref_file = 'referral_data.json'
            if os.path.exists(ref_file):
                with open(ref_file, 'r') as f:
                    ref_data = json.load(f)
                referrer_id = ref_data.get('referred_by', {}).get(str(user_id))
                if referrer_id:
                    house_edge = int(amount * 0.05)
                    bonus = int(house_edge * 0.10)
                    if bonus > 0:
                        self.wallet.add_balance(referrer_id, bonus)
                        # Update earnings
                        earnings = ref_data.get('earnings', {})
                        key = str(referrer_id)
                        earnings[key] = earnings.get(key, 0) + bonus
                        ref_data['earnings'] = earnings
                        with open(ref_file, 'w') as f:
                            json.dump(ref_data, f, indent=2)
        except Exception:
            pass

    # ==================== COINFLIP ====================
    @app_commands.command(name="coinflip", description="Flip a coin - heads or tails!")
    @app_commands.describe(choice="Heads or Tails", bet="Bet amount (e.g. 100k, 1m)")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    async def coinflip(self, interaction: discord.Interaction, choice: str, bet: str):
        # Defer FIRST to prevent timeout
        await interaction.response.defer()

        amount, err = self._check_bet(interaction.user.id, 'coinflip', bet, interaction=None)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        self._deduct(interaction.user.id, 'coinflip', amount)

        result = self.games['coinflip'].play(amount, choice)
        won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
        game_id = self.history.next_id()
        flip_result = result['result']

        if won:
            self.wallet.add_balance(interaction.user.id, payout)

        self.stats.record_game(interaction.user.id, 'coinflip', amount, won, payout)
        label = "WIN" if won else "LOSS"
        self.history.add_result('coinflip', f"#{game_id} {flip_result.upper()} - {label}")

        # Pick the right GIF based on result
        gif_name = f"dice_destiny_realflip_{flip_result}_transparent.gif"
        gif_path = os.path.join(ASSETS_DIR, gif_name)

        embed = discord.Embed(title=f"🪙 Coinflip #{game_id} - {label}", color=COLOR_WIN if won else COLOR_LOSS)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Selected", value=choice.title(), inline=True)
        embed.add_field(name="Flipped", value=flip_result.title(), inline=True)
        embed.add_field(name="Won" if won else "Lost", value=f"{payout:,} GP" if won else f"{amount:,} GP", inline=True)
        hist = self.history.format_history('coinflip')
        if hist != "No games yet":
            embed.add_field(name="Last 10 Flips", value=hist, inline=False)
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        # Attach GIF and show in embed
        if os.path.exists(gif_path):
            file = discord.File(gif_path, filename=gif_name)
            embed.set_image(url=f"attachment://{gif_name}")
            await interaction.followup.send(embed=embed, file=file, view=ResultButtons(seeds))
        else:
            await interaction.followup.send(embed=embed, view=ResultButtons(seeds))

        await self.game_logger.log_game(interaction.user, 'coinflip', amount, won, payout)

    # ==================== HOT/COLD ====================
    @app_commands.command(name="hotcold", description="Plant a flower - pick hot, cold, or a specific color!")
    @app_commands.describe(bet="Bet amount (e.g. 100k, 1m)")
    async def hotcold(self, interaction: discord.Interaction, bet: str):
        amount, err = self._check_bet(interaction.user.id, 'hotcold', bet, interaction=interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        guild = interaction.guild
        embed = discord.Embed(title="🌸 Hot/Cold - Pick your flower!", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(
            name="Payouts",
            value=f"🔥 **Hot** - 2x | ❄️ **Cold** - 2.1x\n"
                  f"Single flower - 6x | Assorted - 9x\n"
                  f"{flower_emoji(guild, 'black')} Black - **400x** | {flower_emoji(guild, 'white')} White - **800x**",
            inline=False
        )
        embed.set_footer(text="Dice & Destiny • Pick a flower!")

        view = HotColdChoiceView(interaction.user, amount, guild, self)
        await interaction.response.send_message(embed=embed, view=view)

    # ==================== FLOWER POKER ====================
    @app_commands.command(name="flowerpoker", description="5 flowers planted - best poker hand wins!")
    @app_commands.describe(choice="Bet on player, host, or draw", bet="Bet amount")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Player - 2x", value="player"),
        app_commands.Choice(name="Host - 2x", value="host"),
        app_commands.Choice(name="Draw - 9x", value="draw"),
    ])
    async def flowerpoker(self, interaction: discord.Interaction, choice: str, bet: str):
        await interaction.response.defer()
        amount, err = self._check_bet(interaction.user.id, 'flowerpoker', bet, interaction=None)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        self._deduct(interaction.user.id, 'flowerpoker', amount)

        guild = interaction.guild
        result = self.games['flowerpoker'].play(amount, choice)
        won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
        winner = result.get('winner', '?')
        is_draw = result.get('is_draw', False)
        p_flowers = result.get('player_flowers', [])
        h_flowers = result.get('host_flowers', [])
        game_id = self.history.next_id()
        hidden = "⬛"

        # Animated reveal - start hidden
        embed = discord.Embed(title=f"🌸 Flower Poker #{game_id} - Planting...", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Bet On", value=choice.title(), inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(name=f"{interaction.user.name}'s Hand", value=" ".join([hidden]*5), inline=False)
        embed.add_field(name="Host's Hand", value=" ".join([hidden]*5), inline=False)
        embed.set_footer(text="Planting flowers...")

        msg = await interaction.followup.send(embed=embed, wait=True)

        # Reveal 1 by 1
        for i in range(5):
            await asyncio.sleep(0.8)
            pr = [flower_emoji(guild, f) for f in p_flowers[:i+1]] + [hidden]*(4-i)
            hr = [flower_emoji(guild, f) for f in h_flowers[:i+1]] + [hidden]*(4-i)
            embed = discord.Embed(title=f"🌸 Flower Poker #{game_id} - Planting...", color=COLOR_GOLD)
            embed.add_field(name="Player", value=interaction.user.mention, inline=True)
            embed.add_field(name="Bet On", value=choice.title(), inline=True)
            embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
            embed.add_field(name=f"{interaction.user.name}'s Hand", value=" ".join(pr), inline=False)
            embed.add_field(name="Host's Hand", value=" ".join(hr), inline=False)
            embed.set_footer(text=f"Planting flower {i+1}/5...")
            await msg.edit(embed=embed)

        await asyncio.sleep(0.5)

        # Final result
        if is_draw and choice != 'draw':
            self.wallet.add_balance(interaction.user.id, amount)
            color, lbl = COLOR_PUSH, "REPLANT"
            self.history.add_result('flowerpoker', f"#{game_id} DRAW (replant)")
            self.stats.record_game(interaction.user.id, 'flowerpoker', amount, True, amount)
        elif won:
            self.wallet.add_balance(interaction.user.id, payout)
            color, lbl = COLOR_WIN, "WIN"
            self.history.add_result('flowerpoker', f"#{game_id} {winner.upper()} - WIN ({choice})")
            self.stats.record_game(interaction.user.id, 'flowerpoker', amount, True, payout)
        else:
            color, lbl = COLOR_LOSS, "LOSS"
            self.history.add_result('flowerpoker', f"#{game_id} {winner.upper()} - LOSS ({choice})")
            self.stats.record_game(interaction.user.id, 'flowerpoker', amount, False, 0)

        pf = " ".join(flower_emoji(guild, f) for f in p_flowers)
        hf = " ".join(flower_emoji(guild, f) for f in h_flowers)

        embed = discord.Embed(title=f"🌸 Flower Poker #{game_id} - Result: {lbl}", color=color)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Bet On", value=choice.title(), inline=True)
        embed.add_field(name="Winner", value=winner.title(), inline=True)
        if is_draw and choice != 'draw':
            embed.add_field(name="Refund", value=f"{amount:,} GP", inline=True)
        elif won:
            embed.add_field(name="Won", value=f"{payout:,} GP", inline=True)
        else:
            embed.add_field(name="Lost", value=f"{amount:,} GP", inline=True)
        embed.add_field(name=f"{interaction.user.name}'s Hand ({result.get('player_hand', '?')})", value=pf, inline=False)
        embed.add_field(name=f"Host's Hand ({result.get('host_hand', '?')})", value=hf, inline=False)
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await msg.edit(embed=embed, view=ResultButtons(seeds))
        await self.game_logger.log_game(interaction.user, 'flowerpoker', amount, won, payout if won else 0)

    # ==================== CASKETS ====================
    @app_commands.command(name="caskets", description="Open a casket - pick your tier!")
    @app_commands.describe(bet="Bet amount (e.g. 100k, 1m)")
    async def caskets(self, interaction: discord.Interaction, bet: str):
        amount, err = self._check_bet(interaction.user.id, 'caskets', bet, interaction=interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        guild = interaction.guild
        embed = discord.Embed(title="📦 Choose your Casket", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(
            name="Tiers",
            value=f"{casket_emoji(guild, 'coin')} **Coin** - 1.9x\n"
                  f"{casket_emoji(guild, 'gem')} **Gem** - 2.5x\n"
                  f"{casket_emoji(guild, 'rare')} **Rare** - 5x",
            inline=False
        )
        embed.set_footer(text="Dice & Destiny • Pick a casket!")

        view = CasketChoiceView(interaction.user, amount, guild, self)
        await interaction.response.send_message(embed=embed, view=view)

    # ==================== DICE ====================
    @app_commands.command(name="dice", description="Roll 1-100 - Under, Mid, or Over!")
    @app_commands.describe(bet="Bet amount (e.g. 100k, 1m)")
    async def dice(self, interaction: discord.Interaction, bet: str):
        amount, err = self._check_bet(interaction.user.id, 'dice', bet, interaction=interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        guild = interaction.guild
        embed = discord.Embed(title="🎲 Dice - Pick your range!", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(
            name="Ranges",
            value="⬇️ **Under** (1-42): **1.9x**\n"
                  "↔️ **Mid** (43-58): **3.1x**\n"
                  "⬆️ **Over** (59-100): **1.9x**",
            inline=False
        )
        embed.set_footer(text="Dice & Destiny • Pick a range!")

        view = DiceChoiceView(interaction.user, amount, guild, self)
        await interaction.response.send_message(embed=embed, view=view)

    # ==================== ROULETTE ====================
    @app_commands.command(name="roulette", description="Spin the roulette wheel!")
    @app_commands.describe(bet="Bet amount (e.g. 100k, 1m)")
    async def roulette(self, interaction: discord.Interaction, bet: str):
        amount, err = self._check_bet(interaction.user.id, 'roulette', bet, interaction=interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        embed = discord.Embed(title="🎰 Roulette - Place your bet!", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.set_footer(text="Choose where to place your chip!")

        view = RouletteChoiceView(interaction.user, amount, self)
        await interaction.response.send_message(embed=embed, view=view)

    async def _play_roulette(self, channel, user, amount, choice):
        """Internal roulette play logic - called by buttons"""
        result = self.games['roulette'].play(amount, choice)
        won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
        number, color_name = result['number'], result['color']
        game_id = self.history.next_id()

        if won:
            self.wallet.add_balance(user.id, payout)

        self.stats.record_game(user.id, 'roulette', amount, won, payout)
        label = "WIN" if won else "LOSS"
        ce = "🔴" if color_name == 'red' else "⚫" if color_name == 'black' else "🟢"
        self.history.add_result('roulette', f"#{game_id} {ce}{number} - {label}")

        recent_nums = []
        raw_hist = self.history.get_history('roulette', 8)
        for entry in raw_hist:
            nums = ''.join(c for c in entry if c.isdigit())
            if nums:
                try:
                    recent_nums.append(int(nums[:2].strip()))
                except ValueError:
                    pass

        user_stats = self.stats.get_user_stats(user.id)

        gif_buf = render_roulette_gif(
            game_id=game_id, bettor=user.name, chip=amount,
            bet_type=choice, winning_number=number, won=won, payout=payout,
            recent_results=recent_nums, streak=0,
            biggest_win=user_stats.get('total_won', 0),
            total_wagered=user_stats.get('total_wagered', 0)
        )
        file = discord.File(gif_buf, filename="roulette.gif")

        embed = discord.Embed(
            title=f"🎰 Roulette #{game_id} - {label}",
            description=f"**{ce} {number} ({color_name.upper()})** | Bet: {choice.replace('_', ' ').title()}",
            color=COLOR_WIN if won else COLOR_LOSS
        )
        embed.add_field(name="Player", value=user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        if won:
            mult = payout / amount if amount > 0 else 0
            embed.add_field(name="Won", value=f"**{payout:,} GP** ({mult:.1f}x)", inline=True)
        else:
            embed.add_field(name="Lost", value=f"{amount:,} GP", inline=True)
        embed.set_image(url="attachment://roulette.gif")
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await channel.send(embed=embed, file=file, view=ResultButtons(seeds))
        await self.game_logger.log_game(user, 'roulette', amount, won, payout)

    # ==================== 99x ====================
    @app_commands.command(name="99x", description="Pick a number 1-100 - match = 99x payout!")
    @app_commands.describe(number="Your number (1-100)", bet="Bet amount")
    async def ninetynine(self, interaction: discord.Interaction, number: int, bet: str):
        if number < 1 or number > 100:
            await interaction.response.send_message("Number must be 1-100!", ephemeral=True)
            return

        await interaction.response.defer()
        amount, err = self._check_bet(interaction.user.id, 'ninetynine', bet, interaction=None)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        self._deduct(interaction.user.id, 'ninetynine', amount)

        result = self.games['ninetynine'].play(amount, 'exact', number=number)
        won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
        game_id = self.history.next_id()

        if won:
            self.wallet.add_balance(interaction.user.id, payout)

        self.stats.record_game(interaction.user.id, 'ninetynine', amount, won, payout)
        label = "WIN" if won else "LOSS"
        self.history.add_result('ninetynine', f"#{game_id} Picked: {number} Rolled: {result['roll']} - {label}")

        embed = discord.Embed(title=f"🍀 99x #{game_id} - {label}", color=COLOR_WIN if won else COLOR_LOSS)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Your Number", value=str(number), inline=True)
        embed.add_field(name="Result", value=str(result['roll']), inline=True)
        if won:
            embed.add_field(name="Won", value=f"{payout:,} GP (99x)", inline=True)
        else:
            embed.add_field(name="Lost", value=f"{amount:,} GP", inline=True)
        hist = self.history.format_history('ninetynine')
        if hist != "No games yet":
            embed.add_field(name="Last 10 Rolls", value=hist, inline=False)
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        # 99x animated frame GIF
        gif_buf = render_99x_gif(result['roll'], 'green' if won else 'red')
        file = discord.File(gif_buf, filename="99x_roll.gif")
        embed.set_image(url="attachment://99x_roll.gif")

        await interaction.followup.send(embed=embed, file=file, view=ResultButtons(seeds))
        await self.game_logger.log_game(interaction.user, 'ninetynine', amount, won, payout)

    # ==================== BLACKJACK ====================
    @app_commands.command(name="blackjack", description="Beat the dealer! Win: 1.9x, Blackjack: 2.5x")
    @app_commands.describe(bet="Bet amount")
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        await interaction.response.defer()
        amount, err = self._check_bet(interaction.user.id, 'blackjack', bet, interaction=None)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        self._deduct(interaction.user.id, 'blackjack', amount)

        game = Blackjack(
            win_payout=self.config['game_settings']['blackjack']['win_payout'],
            blackjack_payout=self.config['game_settings']['blackjack']['blackjack_payout']
        )
        result = game.play(amount)
        state = result['state']
        game_id = self.history.next_id()

        if state == 'player_blackjack':
            # Player blackjack - reveal dealer to check push
            won, payout = game.get_payout(state, amount)
            dealer_value = game.calculate_hand_value(result['dealer_hand'])
            if dealer_value == 21:
                # Both blackjack = push
                res = 'push'
                payout = amount  # Refund
                self.wallet.add_balance(interaction.user.id, payout)
                won = False
            else:
                self.wallet.add_balance(interaction.user.id, payout)
                res = 'blackjack'

            self.stats.record_game(interaction.user.id, 'blackjack', amount, won, payout)
            self.history.add_result('blackjack', f"#{game_id} {'BLACKJACK' if res == 'blackjack' else 'PUSH'}")

            buf = render_blackjack_hand(result['player_hand'], result['dealer_hand'], hide_dealer=False, result=res)
            file = discord.File(buf, filename="blackjack.png")

            embed = discord.Embed(title=f"🃏 Blackjack #{game_id} - {'BLACKJACK!' if res == 'blackjack' else 'PUSH'}", color=COLOR_WIN if res == 'blackjack' else COLOR_GOLD)
            embed.add_field(name="Player", value=interaction.user.mention, inline=True)
            embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
            if res == 'blackjack':
                embed.add_field(name="Won", value=f"**{payout:,} GP**", inline=True)
            else:
                embed.add_field(name="Push", value=f"Refunded {amount:,} GP", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            embed.set_footer(text="Dice & Destiny • Provably Fair")

            await interaction.followup.send(embed=embed, file=file, view=ResultButtons({}))
            await self.game_logger.log_game(interaction.user, 'blackjack', amount, won, payout)
        else:
            # Playing - dealer card stays face down even if dealer has 21
            buf = render_blackjack_hand(result['player_hand'], result['dealer_hand'], hide_dealer=True)
            file = discord.File(buf, filename="blackjack.png")

            embed = discord.Embed(title=f"🃏 Blackjack #{game_id}", color=COLOR_GOLD)
            embed.add_field(name="Player", value=interaction.user.mention, inline=True)
            embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
            embed.add_field(name="Your Hand", value=f"**{result['player_value']}**", inline=True)
            embed.set_image(url="attachment://blackjack.png")

            # Insurance available if dealer shows Ace
            if result.get('dealer_shows_ace'):
                embed.set_footer(text="Dealer shows Ace! Insurance available.")
            else:
                embed.set_footer(text="Hit, Stand, or Double Down!")

            dealer_shows_ace = result.get('dealer_shows_ace', False)
            can_split = result.get('can_split', False)
            view = BlackjackPlayView(interaction.user, game, amount, game_id, self,
                                     dealer_shows_ace=dealer_shows_ace, can_split=can_split)
            await interaction.followup.send(embed=embed, file=file, view=view)

    # ==================== MINES ====================
    @app_commands.command(name="mines", description="Reveal tiles, avoid mines! Cash out anytime.")
    @app_commands.describe(mine_count="Number of mines", bet="Bet amount")
    @app_commands.choices(mine_count=[
        app_commands.Choice(name="3 Mines (Easy)", value=3),
        app_commands.Choice(name="5 Mines", value=5),
        app_commands.Choice(name="7 Mines", value=7),
        app_commands.Choice(name="10 Mines", value=10),
        app_commands.Choice(name="12 Mines (Hard)", value=12),
        app_commands.Choice(name="24 Mines (Insane)", value=24),
    ])
    async def mines(self, interaction: discord.Interaction, mine_count: int, bet: str):
        if interaction.user.id in self.active_mines:
            await interaction.response.send_message("You have an active mines game! Use /cashout first.", ephemeral=True)
            return

        await interaction.response.defer()
        amount, err = self._check_bet(interaction.user.id, 'mines', bet, interaction=None)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return

        self._deduct(interaction.user.id, 'mines', amount)

        mine_game = Mines()
        mine_game.start(amount, mine_count)
        self.active_mines[interaction.user.id] = {'game': mine_game, 'bet': amount}

        # Message 1: Grid with 5x5 buttons
        embed = self._mines_embed(mine_game, amount, interaction.user)
        grid_view = MinesGridView(interaction.user, mine_game, amount, self)
        grid_msg = await interaction.followup.send(embed=embed, view=grid_view, wait=True)

        # Message 2: Cashout button (disabled until first tile)
        co_embed = discord.Embed(title="💰 Cashout", description="Reveal at least 1 tile first!", color=COLOR_GOLD)
        co_view = MinesCashoutView(interaction.user, mine_game, amount, self, grid_msg=grid_msg)
        cashout_msg = await interaction.channel.send(embed=co_embed, view=co_view)

        # Link both messages
        grid_view.cashout_msg = cashout_msg
        self.active_mines[interaction.user.id]['cashout_msg'] = cashout_msg
        self.active_mines[interaction.user.id]['grid_msg'] = grid_msg

    @app_commands.command(name="cashout", description="Cash out your current mines game")
    async def cashout(self, interaction: discord.Interaction):
        if interaction.user.id not in self.active_mines:
            await interaction.response.send_message("No active mines game!", ephemeral=True)
            return

        data = self.active_mines[interaction.user.id]
        mine_game, amount = data['game'], data['bet']
        result = mine_game.cashout()
        if not result:
            await interaction.response.send_message("Reveal at least 1 tile first!", ephemeral=True)
            return

        del self.active_mines[interaction.user.id]
        self.wallet.add_balance(interaction.user.id, result['payout'])
        game_id = self.history.next_id()
        self.history.add_result('mines', f"#{game_id} WIN {result['multiplier']}x - {result['tiles_revealed']} tiles")
        self.stats.record_game(interaction.user.id, 'mines', amount, True, result['payout'])

        embed = discord.Embed(
            title=f"💎 Mines #{game_id} - WIN",
            description=f"{interaction.user.mention} cashed out after {result['tiles_revealed']} tiles!",
            color=COLOR_WIN
        )
        embed.add_field(name="Multiplier", value=f"{result['multiplier']}x", inline=True)
        embed.add_field(name="Payout", value=f"{result['payout']:,} GP", inline=True)
        embed.add_field(name="Profit", value=f"+{result['payout'] - amount:,} GP", inline=True)
        embed.add_field(name="Grid", value=self._mines_grid_text(mine_game), inline=False)
        seeds = result['seeds']
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await interaction.response.send_message(embed=embed, view=ResultButtons(seeds))
        await self.game_logger.log_game(interaction.user, 'mines', amount, True, result['payout'])

    def _mines_embed(self, mine_game, amount, user):
        mult = mine_game._get_multiplier() if mine_game.tiles_revealed > 0 else 1.0
        embed = discord.Embed(title="💎 MINES", color=COLOR_GOLD)
        embed.add_field(name="Player", value=user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(name="Mines", value=str(mine_game.mine_count), inline=True)
        if mine_game.tiles_revealed > 0:
            embed.add_field(name="Multiplier", value=f"{mult}x", inline=True)
            embed.add_field(name="Payout", value=f"{int(amount * mult):,} GP", inline=True)
        embed.set_footer(text="Click tiles to reveal • /cashout to collect")
        return embed

    # ==================== DICE DUEL ====================
    @app_commands.command(name="diceduel", description="Dice duel - vs House or open for anyone to join!")
    @app_commands.describe(bet="Bet amount")
    async def diceduel(self, interaction: discord.Interaction, bet: str):
        amount, err = self._check_bet(interaction.user.id, 'diceduel', bet, interaction=interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        embed = discord.Embed(title="🎲 DICE DUEL", color=COLOR_GOLD)
        embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{amount:,} GP", inline=True)
        embed.add_field(
            name="Choose your opponent",
            value="🏠 **vs House** - Play against Dice & Destiny (1.9x)\n"
                  "⚔️ **Open Duel** - Anyone can join! Winner takes the pot.",
            inline=False
        )
        embed.set_footer(text="Dice & Destiny • Pick your opponent!")

        view = DiceDuelModeView(interaction.user, amount, self)
        await interaction.response.send_message(embed=embed, view=view)

class DiceDuelModeView(discord.ui.View):
    """Choose vs House or Open Duel"""
    def __init__(self, user, amount, cog):
        super().__init__(timeout=60)
        self.user = user
        self.amount = amount
        self.cog = cog
        self.chosen = False

    @discord.ui.button(label="vs House (1.9x)", style=discord.ButtonStyle.primary, emoji="🏠")
    async def vs_house(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Use `/diceduel` to start your own!", ephemeral=True)
            return
        if self.chosen:
            return
        self.chosen = True

        if not self.cog.wallet.has_balance(self.user.id, self.amount):
            await interaction.response.send_message("Insufficient balance!", ephemeral=True)
            self.chosen = False
            return
        self.cog._deduct(self.user.id, 'diceduel', self.amount)
        await interaction.response.defer()

        # Play vs house
        result = self.cog.games['diceduel'].play(self.amount)
        won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
        game_id = self.cog.history.next_id()
        channel = interaction.channel

        if won:
            self.cog.wallet.add_balance(self.user.id, payout)

        self.cog.stats.record_game(self.user.id, 'diceduel', self.amount, won, payout)
        label = "WIN" if won else "LOSS"
        self.cog.history.add_result('diceduel',
            f"#{game_id} {self.user.name} {result['player_roll']} vs House {result['house_roll']} - {label}")

        # Player roll GIF
        gif1 = render_orb_gif(result['player_roll'], 'green' if won else 'red')
        file1 = discord.File(gif1, filename="roll.gif")
        embed = discord.Embed(
            title=f"🎲 Dice Duel #{game_id} vs House - {label}",
            color=COLOR_WIN if won else COLOR_LOSS
        )
        embed.add_field(name="Player", value=self.user.mention, inline=True)
        embed.add_field(name="Opponent", value="House", inline=True)
        embed.add_field(
            name="Rolls",
            value=f"🎲 {self.user.mention}: **{result['player_roll']}**\n🏠 House: **{result['house_roll']}**",
            inline=False
        )
        if won:
            embed.add_field(name="Won", value=f"{payout:,} GP", inline=True)
        else:
            embed.add_field(name="Lost", value=f"{self.amount:,} GP", inline=True)
        embed.set_image(url="attachment://roll.gif")
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await interaction.followup.send(embed=embed, file=file1, view=ResultButtons(seeds))
        await self.cog.game_logger.log_game(self.user, 'diceduel', self.amount, won, payout)

    @discord.ui.button(label="Open Duel", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def open_duel(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Use `/diceduel` to start your own!", ephemeral=True)
            return
        if self.chosen:
            return
        self.chosen = True

        if not self.cog.wallet.has_balance(self.user.id, self.amount):
            await interaction.response.send_message("Insufficient balance!", ephemeral=True)
            self.chosen = False
            return

        # Remove the mode selection buttons
        await interaction.response.edit_message(view=None)

        # Send a NEW message for the join phase
        embed = discord.Embed(title="⚔️ DICE DUEL - Waiting for opponent...", color=COLOR_GOLD)
        embed.add_field(name="Challenger", value=self.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{self.amount:,} GP each", inline=True)
        embed.add_field(name="Pot", value=f"**{self.amount * 2:,} GP**", inline=True)
        embed.add_field(name="Rules", value="Both roll 1-100. Highest roll wins the pot!\nClick **Join Duel** to play!", inline=False)
        embed.set_footer(text="2 minutes to join before it expires")

        view = DiceDuelJoinView(self.user, self.amount, self.cog)
        msg = await interaction.channel.send(embed=embed, view=view)
        view._message = msg


class DiceDuelJoinView(discord.ui.View):
    """Open duel - anyone can join"""
    def __init__(self, challenger, amount, cog):
        super().__init__(timeout=120)
        self.challenger = challenger
        self.amount = amount
        self.cog = cog
        self.resolved = False
        self._message = None

    @discord.ui.button(label="Join Duel!", style=discord.ButtonStyle.success, emoji="🎲")
    async def join(self, interaction, button):
        if interaction.user.id == self.challenger.id:
            await interaction.response.send_message("You can't join your own duel!", ephemeral=True)
            return
        if interaction.user.bot:
            return
        if self.resolved:
            await interaction.response.send_message("Duel already started!", ephemeral=True)
            return
        self.resolved = True
        opponent = interaction.user

        # Check both balances
        if not self.cog.wallet.has_balance(self.challenger.id, self.amount):
            await interaction.response.edit_message(
                content=f"Duel cancelled - {self.challenger.mention} doesn't have enough GP!", embed=None, view=None)
            return
        if not self.cog.wallet.has_balance(opponent.id, self.amount):
            await interaction.response.send_message("You don't have enough GP!", ephemeral=True)
            self.resolved = False
            return

        # Deduct both
        self.cog._deduct(self.challenger.id, 'diceduel', self.amount)
        self.cog._deduct(opponent.id, 'diceduel', self.amount)

        await interaction.response.defer()

        # Roll for both
        from provably_fair import ProvablyFair
        pf = ProvablyFair()
        roll1 = (pf.roll(100)) + 1
        roll2 = (pf.roll(100)) + 1
        while roll1 == roll2:
            roll1 = (pf.roll(100)) + 1
            roll2 = (pf.roll(100)) + 1
        seeds = pf.get_seeds()

        pot = self.amount * 2
        game_id = self.cog.history.next_id()
        channel = interaction.channel

        # Update to "Rolling..."
        rolling_embed = discord.Embed(title=f"⚔️ Dice Duel #{game_id} - ROLLING...", color=COLOR_GOLD)
        rolling_embed.add_field(name="Challenger", value=self.challenger.mention, inline=True)
        rolling_embed.add_field(name="Opponent", value=opponent.mention, inline=True)
        rolling_embed.add_field(name="Pot", value=f"**{pot:,} GP**", inline=True)
        await interaction.message.edit(embed=rolling_embed, view=None)

        # Roll 1 - Challenger
        gif1 = render_orb_gif(roll1, None)
        file1 = discord.File(gif1, filename="roll1.gif")
        embed1 = discord.Embed(title=f"🎲 {self.challenger.name} rolls...", color=COLOR_GOLD)
        embed1.set_image(url="attachment://roll1.gif")
        await channel.send(embed=embed1, file=file1)

        await asyncio.sleep(3)

        # Roll 2 - Opponent
        gif2 = render_orb_gif(roll2, None)
        file2 = discord.File(gif2, filename="roll2.gif")
        embed2 = discord.Embed(title=f"🎲 {opponent.name} rolls...", color=COLOR_GOLD)
        embed2.set_image(url="attachment://roll2.gif")
        await channel.send(embed=embed2, file=file2)

        await asyncio.sleep(3)

        # Winner
        if roll1 > roll2:
            winner, loser = self.challenger, opponent
        else:
            winner, loser = opponent, self.challenger

        self.cog.wallet.add_balance(winner.id, pot)
        self.cog.stats.record_game(winner.id, 'diceduel', self.amount, True, pot)
        self.cog.stats.record_game(loser.id, 'diceduel', self.amount, False, 0)
        self.cog.history.add_result('diceduel',
            f"#{game_id} {self.challenger.name} {roll1} vs {opponent.name} {roll2}")

        result_embed = discord.Embed(
            title=f"⚔️ Dice Duel #{game_id} - {winner.name} WINS!",
            color=COLOR_WIN
        )
        result_embed.add_field(name="Challenger", value=self.challenger.mention, inline=True)
        result_embed.add_field(name="Opponent", value=opponent.mention, inline=True)
        result_embed.add_field(name="Pot", value=f"**{pot:,} GP**", inline=True)
        result_embed.add_field(
            name="Rolls",
            value=f"🎲 {self.challenger.mention}: **{roll1}**\n🎲 {opponent.mention}: **{roll2}**",
            inline=False
        )
        result_embed.add_field(
            name="Result",
            value=f"**{winner.mention}** wins **{pot:,} GP**!",
            inline=False
        )
        result_embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await channel.send(embed=result_embed, view=ResultButtons(seeds))
        await self.cog.game_logger.log_game(winner, 'diceduel', self.amount, True, pot)

    async def on_timeout(self):
        if not self.resolved:
            self.resolved = True
            # Try to edit the message to show expired
            try:
                if self._message:
                    embed = discord.Embed(title="⚔️ DICE DUEL - Expired", description="No one joined in time.", color=COLOR_LOSS)
                    await self._message.edit(embed=embed, view=None)
            except Exception:
                pass

    def _mines_grid_text(self, mine_game):
        grid = mine_game.get_grid_display()
        text = ""
        for row in grid:
            for cell in row:
                if cell == 'safe':
                    text += "💎 "
                elif cell in ('mine', 'mine_hidden'):
                    text += "💣 "
                else:
                    text += "⬛ "
            text += "\n"
        return text


class RouletteChoiceView(discord.ui.View):
    """Roulette bet buttons"""
    def __init__(self, user, amount, cog):
        super().__init__(timeout=60)
        self.user = user
        self.amount = amount
        self.cog = cog
        self.chosen = False

        bets = [
            ('Red 1.85x', 'red', discord.ButtonStyle.danger, '🔴', 0),
            ('Black 1.85x', 'black', discord.ButtonStyle.secondary, '⚫', 0),
            ('Even 1.85x', 'even', discord.ButtonStyle.primary, '2️⃣', 0),
            ('Odd 1.85x', 'odd', discord.ButtonStyle.primary, '1️⃣', 0),
            ('1-18 1.85x', 'low', discord.ButtonStyle.success, '⬇️', 1),
            ('19-36 1.85x', 'high', discord.ButtonStyle.success, '⬆️', 1),
            ('1st 12 2.78x', 'dozen1', discord.ButtonStyle.secondary, '1️⃣', 2),
            ('2nd 12 2.78x', 'dozen2', discord.ButtonStyle.secondary, '2️⃣', 2),
            ('3rd 12 2.78x', 'dozen3', discord.ButtonStyle.secondary, '3️⃣', 2),
            ('Number 33x', 'pick_number', discord.ButtonStyle.primary, '🎯', 3),
        ]
        for label, value, style, emoji, row in bets:
            if value == 'pick_number':
                btn = discord.ui.Button(label=label, style=style, emoji=emoji, row=row)
                btn.callback = self._pick_number_cb
                self.add_item(btn)
            else:
                btn = discord.ui.Button(label=label, style=style, emoji=emoji, row=row)
                btn.callback = self._make_cb(value)
                self.add_item(btn)

    async def _pick_number_cb(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your bet!", ephemeral=True)
            return
        if self.chosen:
            await interaction.response.send_message("Already placed!", ephemeral=True)
            return
        await interaction.response.send_modal(RouletteNumberModal(self.user, self.amount, self.cog, self))

    def _make_cb(self, choice):
        async def cb(interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Not your bet!", ephemeral=True)
                return
            if self.chosen:
                await interaction.response.send_message("Already placed!", ephemeral=True)
                return
            self.chosen = True

            if not self.cog.wallet.has_balance(self.user.id, self.amount):
                await interaction.response.send_message("Insufficient balance!", ephemeral=True)
                self.chosen = False
                return
            self.cog._deduct(self.user.id, 'roulette', self.amount)
            await interaction.response.defer()

            await self.cog._play_roulette(interaction.channel, self.user, self.amount, choice)
        return cb


class RouletteNumberModal(discord.ui.Modal, title="Pick a Number (0-36)"):
    def __init__(self, user, amount, cog, parent_view):
        super().__init__()
        self.user = user
        self.amount = amount
        self.cog = cog
        self.parent_view = parent_view
        self.number_input = discord.ui.TextInput(
            label="Number (0-36)", placeholder="e.g. 17", required=True, max_length=2
        )
        self.add_item(self.number_input)

    async def on_submit(self, interaction):
        try:
            number = int(self.number_input.value)
        except ValueError:
            await interaction.response.send_message("Invalid number!", ephemeral=True)
            return
        if number < 0 or number > 36:
            await interaction.response.send_message("Must be 0-36!", ephemeral=True)
            return

        self.parent_view.chosen = True

        if not self.cog.wallet.has_balance(self.user.id, self.amount):
            await interaction.response.send_message("Insufficient balance!", ephemeral=True)
            self.parent_view.chosen = False
            return
        self.cog._deduct(self.user.id, 'roulette', self.amount)
        await interaction.response.defer()

        # Play roulette with number bet
        result = self.cog.games['roulette'].play(self.amount, 'number', bet_value=number)
        won = result['won']
        payout = result['payout']
        seeds = result.get('seeds', {})
        win_number = result['number']
        color_name = result['color']
        game_id = self.cog.history.next_id()

        if won:
            self.cog.wallet.add_balance(self.user.id, payout)

        self.cog.stats.record_game(self.user.id, 'roulette', self.amount, won, payout)
        label = "WIN" if won else "LOSS"
        ce = "🔴" if color_name == 'red' else "⚫" if color_name == 'black' else "🟢"
        self.cog.history.add_result('roulette', f"#{game_id} {ce}{win_number} - {label}")

        recent_nums = []
        raw_hist = self.cog.history.get_history('roulette', 8)
        for entry in raw_hist:
            nums = ''.join(c for c in entry if c.isdigit())
            if nums:
                try:
                    recent_nums.append(int(nums[:2].strip()))
                except ValueError:
                    pass

        user_stats = self.cog.stats.get_user_stats(self.user.id)

        gif_buf = render_roulette_gif(
            game_id=game_id, bettor=self.user.name, chip=self.amount,
            bet_type=f'number_{number}', winning_number=win_number, won=won, payout=payout,
            recent_results=recent_nums, streak=0,
            biggest_win=user_stats.get('total_won', 0),
            total_wagered=user_stats.get('total_wagered', 0)
        )
        file = discord.File(gif_buf, filename="roulette.gif")

        embed = discord.Embed(
            title=f"🎰 Roulette #{game_id} - {label}",
            description=f"**{ce} {win_number} ({color_name.upper()})** | Bet: Number {number} (35x)",
            color=COLOR_WIN if won else COLOR_LOSS
        )
        embed.add_field(name="Player", value=self.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{self.amount:,} GP", inline=True)
        if won:
            embed.add_field(name="Won", value=f"**{payout:,} GP** (35x)", inline=True)
        else:
            embed.add_field(name="Lost", value=f"{self.amount:,} GP", inline=True)
        embed.set_image(url="attachment://roulette.gif")
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await interaction.channel.send(embed=embed, file=file, view=ResultButtons(seeds))
        await self.cog.game_logger.log_game(self.user, 'roulette', self.amount, won, payout)


class DiceChoiceView(discord.ui.View):
    """Under / Mid / Over buttons for dice"""
    def __init__(self, user, amount, guild, cog):
        super().__init__(timeout=60)
        self.user = user
        self.amount = amount
        self.guild = guild
        self.cog = cog
        self.chosen = False

        # Build buttons - try custom emojis first
        for bet_type, label, fallback_emoji, style in [
            ('under', 'Under (2.14x)', '⬇️', discord.ButtonStyle.primary),
            ('mid', 'Mid (5.62x)', '↔️', discord.ButtonStyle.success),
            ('over', 'Over (2.14x)', '⬆️', discord.ButtonStyle.danger),
        ]:
            # Try custom emoji from server
            emoji_names = {'under': 'under', 'mid': 'Mid', 'over': 'over'}
            emoji_obj = None
            if guild:
                emoji_obj = discord.utils.get(guild.emojis, name=emoji_names[bet_type])
            if not emoji_obj:
                emoji_obj = fallback_emoji
            btn = discord.ui.Button(style=style, label=label, emoji=emoji_obj)
            btn.callback = self._make_callback(bet_type)
            self.add_item(btn)

    def _make_callback(self, bet_type):
        async def callback(interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return
            if self.chosen:
                await interaction.response.send_message("Already picked!", ephemeral=True)
                return
            self.chosen = True

            if not self.cog.wallet.has_balance(self.user.id, self.amount):
                await interaction.response.send_message("Insufficient balance!", ephemeral=True)
                self.chosen = False
                return
            self.cog._deduct(self.user.id, 'dice', self.amount)

            await interaction.response.defer()

            # Play the game
            result = self.cog.games['dice'].play(self.amount, bet_type=bet_type)
            won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
            roll = result['roll']
            game_id = self.cog.history.next_id()

            if won:
                self.cog.wallet.add_balance(self.user.id, payout)

            self.cog.stats.record_game(self.user.id, 'dice', self.amount, won, payout)
            label = "WIN" if won else "LOSS"
            self.cog.history.add_result('dice', f"#{game_id} Roll: {roll} {bet_type.upper()} - {label}")

            # Animated rolling GIF
            gif_buf = render_orb_gif(roll, 'green' if won else 'red')
            result_file = discord.File(gif_buf, filename="dice_roll.gif")

            embed = discord.Embed(title=f"🎲 Dice Roll #{game_id} - Result: {label}", color=COLOR_WIN if won else COLOR_LOSS)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Rolled", value=f"**{roll}**", inline=True)
            embed.add_field(name="Selected", value=f"{bet_type.upper()} ({result['range']})", inline=True)
            if won:
                embed.add_field(name="Won", value=f"{payout:,} GP ({result['multiplier']}x)", inline=True)
            else:
                embed.add_field(name="Lost", value=f"{self.amount:,} GP", inline=True)
            hist = self.cog.history.format_history('dice')
            if hist != "No games yet":
                embed.add_field(name="Last 10 Rolls", value=hist, inline=False)
            embed.set_image(url="attachment://dice_roll.gif")
            embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

            await interaction.followup.send(embed=embed, file=result_file, view=ResultButtons(seeds))
            await self.cog.game_logger.log_game(self.user, 'dice', self.amount, won, payout)
        return callback


class HotColdChoiceView(discord.ui.View):
    """Hot/Cold buttons with custom flower emojis"""
    def __init__(self, user, amount, guild, cog):
        super().__init__(timeout=60)
        self.user = user
        self.amount = amount
        self.guild = guild
        self.cog = cog
        self.chosen = False

        # Row 0: Hot & Cold
        hot_btn = discord.ui.Button(style=discord.ButtonStyle.danger, label="Hot (2x)", emoji="🔥", row=0)
        hot_btn.callback = self._make_callback('hot')
        self.add_item(hot_btn)

        cold_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Cold (3x)", emoji="❄️", row=0)
        cold_btn.callback = self._make_callback('cold')
        self.add_item(cold_btn)

        # Row 1: Individual flowers with custom emojis
        for color, style in [
            ('red', discord.ButtonStyle.secondary),
            ('blue', discord.ButtonStyle.secondary),
            ('yellow', discord.ButtonStyle.secondary),
            ('orange', discord.ButtonStyle.secondary),
            ('purple', discord.ButtonStyle.secondary),
        ]:
            emoji_name = FLOWER_EMOJI_NAMES.get(color)
            emoji_obj = discord.utils.get(guild.emojis, name=emoji_name) if guild and emoji_name else None
            if not emoji_obj:
                emoji_obj = FLOWER_FALLBACKS.get(color, '🌸')
            btn = discord.ui.Button(style=style, label=color.title(), emoji=emoji_obj, row=1)
            btn.callback = self._make_callback(color)
            self.add_item(btn)

        # Row 2: Mixed, Assorted
        for color, lbl in [('mixed', 'Mixed (6x)'), ('assorted', 'Assorted (9x)')]:
            emoji_name = FLOWER_EMOJI_NAMES.get(color)
            emoji_obj = discord.utils.get(guild.emojis, name=emoji_name) if guild and emoji_name else None
            if not emoji_obj:
                emoji_obj = FLOWER_FALLBACKS.get(color, '🌸')
            btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label=lbl, emoji=emoji_obj, row=2)
            btn.callback = self._make_callback(color)
            self.add_item(btn)

        # Row 3: Black & White (rare)
        for color, lbl, style in [
            ('black', 'Black (400x)', discord.ButtonStyle.secondary),
            ('white', 'White (800x)', discord.ButtonStyle.secondary),
        ]:
            emoji_name = FLOWER_EMOJI_NAMES.get(color)
            emoji_obj = discord.utils.get(guild.emojis, name=emoji_name) if guild and emoji_name else None
            if not emoji_obj:
                emoji_obj = FLOWER_FALLBACKS.get(color, '🌸')
            btn = discord.ui.Button(style=style, label=lbl, emoji=emoji_obj, row=3)
            btn.callback = self._make_callback(color)
            self.add_item(btn)

    def _make_callback(self, choice):
        async def callback(interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return
            if self.chosen:
                await interaction.response.send_message("Already picked!", ephemeral=True)
                return
            self.chosen = True

            if not self.cog.wallet.has_balance(self.user.id, self.amount):
                await interaction.response.send_message("Insufficient balance!", ephemeral=True)
                self.chosen = False
                return
            self.cog._deduct(self.user.id, 'hotcold', self.amount)

            result = self.cog.games['hotcold'].play(self.amount, choice)
            won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
            game_id = self.cog.history.next_id()

            if won:
                self.cog.wallet.add_balance(self.user.id, payout)

            self.cog.stats.record_game(self.user.id, 'hotcold', self.amount, won, payout)
            label = "WIN" if won else "LOSS"
            re = flower_emoji(self.guild, result['result'])
            ce = flower_emoji(self.guild, choice) if choice in FLOWER_EMOJI_NAMES else choice.title()
            self.cog.history.add_result('hotcold', f"#{game_id} {re} {result['result'].upper()} - {label}")

            embed = discord.Embed(title=f"🌸 Hot/Cold #{game_id} - RESULT: {label}", color=COLOR_WIN if won else COLOR_LOSS)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Selected", value=f"{ce} {choice.title()}", inline=True)
            embed.add_field(name="Planted", value=f"{re} {result['result'].title()}", inline=True)
            if won:
                embed.add_field(name="Won", value=f"{payout:,} GP ({result['multiplier']}x)", inline=True)
            else:
                embed.add_field(name="Lost", value=f"{self.amount:,} GP", inline=True)
            hist = self.cog.history.format_history('hotcold')
            if hist != "No games yet":
                embed.add_field(name="Last 10 Planted", value=hist, inline=False)
            embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

            await interaction.response.edit_message(embed=embed, view=ResultButtons(seeds))
            await self.cog.game_logger.log_game(self.user, 'hotcold', self.amount, won, payout if won else 0)
        return callback


class CasketChoiceView(discord.ui.View):
    """Casket tier buttons with custom emojis"""
    def __init__(self, user, amount, guild, cog):
        super().__init__(timeout=60)
        self.user = user
        self.amount = amount
        self.guild = guild
        self.cog = cog
        self.chosen = False

        # Build buttons dynamically to use custom emojis
        for tier, label, style in [
            ('coin', 'Coin (1.9x)', discord.ButtonStyle.primary),
            ('gem', 'Gem (2.5x)', discord.ButtonStyle.success),
            ('rare', 'Rare (5x)', discord.ButtonStyle.danger),
        ]:
            emoji_name = CASKET_EMOJI_NAMES.get(tier)
            emoji_obj = None
            if guild and emoji_name:
                emoji_obj = discord.utils.get(guild.emojis, name=emoji_name)
            if not emoji_obj:
                emoji_obj = CASKET_FALLBACKS.get(tier, '📦')

            btn = discord.ui.Button(style=style, label=label, emoji=emoji_obj)
            btn.callback = self._make_callback(tier)
            self.add_item(btn)

    def _make_callback(self, tier):
        async def callback(interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Not your casket!", ephemeral=True)
                return
            if self.chosen:
                await interaction.response.send_message("Already picked!", ephemeral=True)
                return
            self.chosen = True

            # Check balance again (may have changed since command)
            if not self.cog.wallet.has_balance(self.user.id, self.amount):
                await interaction.response.send_message("Insufficient balance!", ephemeral=True)
                self.chosen = False
                return
            self.cog._deduct(self.user.id, 'caskets', self.amount)

            result = self.cog.games['caskets'].play(self.amount, tier)
            won, payout, seeds = result['won'], result['payout'], result.get('seeds', {})
            game_id = self.cog.history.next_id()

            if won:
                self.cog.wallet.add_balance(self.user.id, payout)

            self.cog.stats.record_game(self.user.id, 'caskets', self.amount, won, payout)
            label = "WIN" if won else "LOSS"
            re = casket_emoji(self.guild, result['result'])
            self.cog.history.add_result('caskets', f"#{game_id} {re} {result['result'].upper()} - {label}")

            picked_emoji = casket_emoji(self.guild, tier)
            embed = discord.Embed(title=f"📦 Caskets #{game_id} - {label}", color=COLOR_WIN if won else COLOR_LOSS)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Picked", value=f"{picked_emoji} {tier.title()}", inline=True)
            embed.add_field(name="Opened", value=f"{re} {result['result'].title()}", inline=True)
            embed.add_field(name="Wagered", value=f"{self.amount:,} GP", inline=True)
            if won:
                embed.add_field(name="Won", value=f"{payout:,} GP", inline=True)
            else:
                embed.add_field(name="Lost", value=f"{self.amount:,} GP", inline=True)
            hist = self.cog.history.format_history('caskets')
            if hist != "No games yet":
                embed.add_field(name="Last 10 Opens", value=hist, inline=False)
            embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

            await interaction.response.edit_message(embed=embed, view=ResultButtons(seeds))
            await self.cog.game_logger.log_game(self.user, 'caskets', self.amount, won, payout)
        return callback

    async def on_timeout(self):
        # Didn't pick - no money was deducted yet so nothing to refund
        pass


class BlackjackPlayView(discord.ui.View):
    """Hit/Stand/Double/Split/Insurance for active blackjack game"""
    def __init__(self, user, game, bet, game_id, cog, dealer_shows_ace=False, can_split=False):
        super().__init__(timeout=120)
        self.user = user
        self.game = game
        self.bet = bet
        self.original_bet = bet
        self.game_id = game_id
        self.cog = cog
        self.insured = False
        self.has_acted = False  # True after first hit - disables double down

        # Add split button if possible
        if can_split:
            split_btn = discord.ui.Button(
                label=f"Split ({bet:,} GP)",
                style=discord.ButtonStyle.primary,
                emoji="✂️",
                row=1
            )
            split_btn.callback = self._split_cb
            self.add_item(split_btn)

        # Add insurance button if dealer shows ace
        if dealer_shows_ace:
            ins_btn = discord.ui.Button(
                label=f"Insurance ({bet // 2:,} GP)",
                style=discord.ButtonStyle.secondary,
                emoji="🛡️",
                row=1
            )
            ins_btn.callback = self._insurance_cb
            self.add_item(ins_btn)

    async def _insurance_cb(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        if self.insured:
            await interaction.response.send_message("Already insured!", ephemeral=True)
            return
        insurance_cost = self.original_bet // 2
        if not self.cog.wallet.has_balance(self.user.id, insurance_cost):
            await interaction.response.send_message("Not enough GP for insurance!", ephemeral=True)
            return
        self.insured = True
        self.cog.wallet.remove_balance(self.user.id, insurance_cost)
        await interaction.response.send_message(
            f"🛡️ Insured for {insurance_cost:,} GP! If dealer has Blackjack, you get 2:1 payout.",
            ephemeral=True
        )

    async def _split_cb(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        if not self.cog.wallet.has_balance(self.user.id, self.original_bet):
            await interaction.response.send_message("Not enough GP to split!", ephemeral=True)
            return
        if not self.game.can_split():
            await interaction.response.send_message("Can't split this hand!", ephemeral=True)
            return

        self.cog.wallet.remove_balance(self.user.id, self.original_bet)
        await interaction.response.defer()

        result = self.game.split()
        if not result:
            await interaction.followup.send("Split failed!", ephemeral=True)
            return

        buf = render_blackjack_hand(
            result['player_hand'], list(self.game.dealer_hand),
            hide_dealer=True, split_cards=result['split_hand'],
            active_hand='main'
        )
        file = discord.File(buf, filename="blackjack.png")

        embed = discord.Embed(title=f"🃏 Blackjack #{self.game_id} - SPLIT!", color=COLOR_GOLD)
        embed.add_field(name="Player", value=self.user.mention, inline=True)
        embed.add_field(name="Wager", value=f"{self.original_bet * 2:,} GP (2 hands)", inline=True)
        embed.add_field(name="Hand 1", value=f"**{result['player_value']}**", inline=True)
        embed.add_field(name="Hand 2", value=f"**{result['split_value']}**", inline=True)
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text="Playing Hand 1 - Hit or Stand!")

        # New view without split/double (can't split again or double after split)
        new_view = BlackjackPlayView(self.user, self.game, self.original_bet, self.game_id, self.cog)
        await interaction.message.edit(embed=embed, view=new_view, attachments=[file])

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        self.has_acted = True  # No more double down after first hit
        result = self.game.hit()
        active = result.get('active_hand', self.game.active_hand)
        active_value = result.get('split_value', 0) if active == 'split' else result['player_value']

        if result['state'] == 'player_bust':
            await self._finish(interaction, result, False)
        elif result['state'] == 'hand1_bust':
            # Hand 1 bust, now playing hand 2
            split = result.get('split_hand')
            buf = render_blackjack_hand(
                result['player_hand'], list(self.game.dealer_hand),
                hide_dealer=True, split_cards=split, active_hand='split'
            )
            file = discord.File(buf, filename="blackjack.png")
            embed = discord.Embed(title=f"🃏 Blackjack #{self.game_id} - Hand 1 BUST!", color=COLOR_LOSS)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Hand 2", value=f"**{result.get('split_value', 0)}**", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            embed.set_footer(text="Playing Hand 2 - Hit or Stand!")
            await interaction.message.edit(embed=embed, view=self, attachments=[file])
        elif active_value == 21:
            # Auto stand on 21
            result = self.game.stand()
            if result['state'] == 'playing':
                # Moved to hand 2 after standing hand 1
                split = result.get('split_hand')
                buf = render_blackjack_hand(
                    result['player_hand'], list(self.game.dealer_hand),
                    hide_dealer=True, split_cards=split, active_hand='split'
                )
                file = discord.File(buf, filename="blackjack.png")
                embed = discord.Embed(title=f"🃏 Blackjack #{self.game_id}", color=COLOR_GOLD)
                embed.add_field(name="Hand 2", value=f"**{result.get('split_value', 0)}**", inline=True)
                embed.set_image(url="attachment://blackjack.png")
                embed.set_footer(text="Playing Hand 2 - Hit or Stand!")
                await interaction.message.edit(embed=embed, view=self, attachments=[file])
            else:
                won = result['state'] in ['dealer_bust', 'player_wins']
                await self._finish(interaction, result, won)
        else:
            split = result.get('split_hand')
            buf = render_blackjack_hand(
                result['player_hand'], list(self.game.dealer_hand),
                hide_dealer=True, split_cards=split, active_hand=active
            )
            file = discord.File(buf, filename="blackjack.png")

            embed = discord.Embed(title=f"🃏 Blackjack #{self.game_id}", color=COLOR_GOLD)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            wager = self.original_bet * 2 if self.game.is_split else self.bet
            embed.add_field(name="Wager", value=f"{wager:,} GP", inline=True)
            hand_label = f"Hand {'1' if active == 'main' else '2'}" if self.game.is_split else "Your Hand"
            embed.add_field(name=hand_label, value=f"**{active_value}**", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            embed.set_footer(text="Hit or Stand!")

            await interaction.message.edit(embed=embed, view=self, attachments=[file])

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger, emoji="✋")
    async def stand(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        result = self.game.stand()

        if result['state'] == 'playing':
            # Split: moved to hand 2
            split = result.get('split_hand')
            buf = render_blackjack_hand(
                result['player_hand'], list(self.game.dealer_hand),
                hide_dealer=True, split_cards=split, active_hand='split'
            )
            file = discord.File(buf, filename="blackjack.png")
            embed = discord.Embed(title=f"🃏 Blackjack #{self.game_id}", color=COLOR_GOLD)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Hand 2", value=f"**{result.get('split_value', 0)}**", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            embed.set_footer(text="Playing Hand 2 - Hit or Stand!")
            await interaction.message.edit(embed=embed, view=self, attachments=[file])
        else:
            won = result['state'] in ['dealer_bust', 'player_wins']
            await self._finish(interaction, result, won)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="💰")
    async def double(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        if self.has_acted:
            await interaction.response.send_message("Double down only on first action!", ephemeral=True)
            return
        if not self.cog.wallet.has_balance(self.user.id, self.bet):
            await interaction.response.send_message("Not enough GP to double!", ephemeral=True)
            return
        await interaction.response.defer()
        self.cog.wallet.remove_balance(self.user.id, self.bet)
        self.bet *= 2
        result = self.game.hit()
        if result['state'] == 'player_bust':
            await self._finish(interaction, result, False)
        else:
            result = self.game.stand()
            won = result['state'] in ['dealer_bust', 'player_wins']
            await self._finish(interaction, result, won)

    async def _finish(self, interaction, result, won):
        payout = 0
        total_payout = 0
        insurance_payout = 0

        # Main hand payout (use self.bet which includes double down)
        if won:
            _, payout = self.game.get_payout(result['state'], self.bet if not self.game.is_split else self.original_bet)
            self.cog.wallet.add_balance(self.user.id, payout)
            total_payout += payout

        res = 'bust' if result['state'] == 'player_bust' else ('win' if won else 'loss')
        if result['state'] == 'push':
            res = 'push'
            refund = self.bet if not self.game.is_split else self.original_bet
            self.cog.wallet.add_balance(self.user.id, refund)
            total_payout += refund
        if result['state'] == 'dealer_blackjack':
            res = 'loss'

        # Split hand payout
        split_payout = 0
        split_res = None
        if self.game.is_split and 'split_state' in result:
            split_state = result['split_state']
            split_won, sp = self.game.get_payout(split_state, self.original_bet)
            if split_won:
                self.cog.wallet.add_balance(self.user.id, sp)
                total_payout += sp
                split_payout = sp
            elif split_state == 'push':
                self.cog.wallet.add_balance(self.user.id, self.original_bet)
                total_payout += self.original_bet
            split_res = 'win' if split_won else ('push' if split_state == 'push' else 'loss')

        # Insurance
        if self.insured:
            dealer_hand = result.get('dealer_hand', self.game.dealer_hand)
            d_val = self.game.calculate_hand_value(dealer_hand)
            if d_val == 21 and len(dealer_hand) == 2:
                insurance_payout = self.original_bet
                self.cog.wallet.add_balance(self.user.id, insurance_payout)
                total_payout += insurance_payout

        total_bet = self.original_bet * 2 if self.game.is_split else self.bet
        self.cog.stats.record_game(self.user.id, 'blackjack', total_bet, total_payout > 0, total_payout)
        self.cog.history.add_result('blackjack', f"#{self.game_id} {result['state'].replace('_',' ').upper()}")

        player_hand = result.get('player_hand', self.game.player_hand)
        dealer_hand = result.get('dealer_hand', self.game.dealer_hand)
        split_hand = result.get('split_hand')

        buf = render_blackjack_hand(
            player_hand, dealer_hand, hide_dealer=False, result=res,
            split_cards=split_hand, split_result=split_res
        )
        file = discord.File(buf, filename="blackjack.png")

        p_val = result.get('player_value', self.game.calculate_hand_value(player_hand))
        d_val = result.get('dealer_value', self.game.calculate_hand_value(dealer_hand))

        # Build title and color based on overall result
        profit = total_payout - total_bet
        if self.game.is_split:
            if profit > 0:
                title_text = "SPLIT RESULT - PROFIT!"
                color = COLOR_WIN
            elif profit == 0:
                title_text = "SPLIT RESULT - BREAK EVEN"
                color = COLOR_GOLD
            else:
                title_text = "SPLIT RESULT - LOSS"
                color = COLOR_LOSS
        else:
            state_text = result['state'].replace('_', ' ').upper()
            if won:
                title_text = state_text
                color = COLOR_WIN
            elif res == 'push':
                title_text = "PUSH"
                color = COLOR_GOLD
            else:
                title_text = state_text
                color = COLOR_LOSS

        embed = discord.Embed(
            title=f"🃏 Blackjack #{self.game_id} - {title_text}",
            color=color
        )
        embed.add_field(name="Player", value=self.user.mention, inline=True)
        embed.add_field(name="Dealer", value=f"**{d_val}**", inline=True)
        embed.add_field(name="Total Wager", value=f"{total_bet:,} GP", inline=True)

        if self.game.is_split:
            # Hand 1 result
            h1_emoji = "✅" if res == 'win' else ("🤝" if res == 'push' else "❌")
            h1_payout_text = f"+{payout:,} GP" if won else ("Refund" if res == 'push' else "Lost")
            embed.add_field(
                name=f"{h1_emoji} Hand 1 ({p_val})",
                value=f"**{res.upper()}** | {h1_payout_text}",
                inline=True
            )

            # Hand 2 result
            s_val = result.get('split_value', 0)
            h2_emoji = "✅" if split_res == 'win' else ("🤝" if split_res == 'push' else "❌")
            h2_payout_text = f"+{split_payout:,} GP" if split_res == 'win' else ("Refund" if split_res == 'push' else "Lost")
            embed.add_field(
                name=f"{h2_emoji} Hand 2 ({s_val})",
                value=f"**{split_res.upper() if split_res else '?'}** | {h2_payout_text}",
                inline=True
            )

            # Total profit/loss
            profit = total_payout - total_bet
            if profit > 0:
                embed.add_field(name="💰 Profit", value=f"**+{profit:,} GP**", inline=True)
            elif profit == 0:
                embed.add_field(name="🤝 Break Even", value="0 GP", inline=True)
            else:
                embed.add_field(name="📉 Net Loss", value=f"**{profit:,} GP**", inline=True)
        else:
            embed.add_field(name="Your Hand", value=f"**{p_val}**", inline=True)
            if total_payout > total_bet:
                embed.add_field(name="Won", value=f"**{total_payout:,} GP**", inline=True)
            elif res == 'push':
                embed.add_field(name="Push", value=f"Refunded {self.original_bet:,} GP", inline=True)
            else:
                embed.add_field(name="Lost", value=f"{total_bet:,} GP", inline=True)

        if insurance_payout > 0:
            embed.add_field(name="🛡️ Insurance", value=f"+{insurance_payout:,} GP", inline=True)

        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text="Dice & Destiny • Provably Fair")

        view = BlackjackResultView(self.user, self.original_bet, self.cog)
        await interaction.message.edit(embed=embed, view=view, attachments=[file])
        await self.cog.game_logger.log_game(self.user, 'blackjack', total_bet, total_payout > 0, total_payout)


class BlackjackResultView(discord.ui.View):
    """Repeat Bet + Verify Fairness after blackjack game"""
    def __init__(self, user, bet, cog):
        super().__init__(timeout=300)
        self.user = user
        self.bet = bet
        self.cog = cog

    @discord.ui.button(label="Repeat Bet", style=discord.ButtonStyle.success, emoji="🔄")
    async def repeat(self, interaction, button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your bet!", ephemeral=True)
            return
        # Check balance
        if not self.cog.wallet.has_balance(self.user.id, self.bet):
            await interaction.response.send_message("Not enough GP!", ephemeral=True)
            return
        # Start new game with same bet
        self.cog._deduct(self.user.id, 'blackjack', self.bet)
        await interaction.response.defer()

        game = Blackjack(
            win_payout=self.cog.config['game_settings']['blackjack']['win_payout'],
            blackjack_payout=self.cog.config['game_settings']['blackjack']['blackjack_payout']
        )
        result = game.play(self.bet)
        game_id = self.cog.history.next_id()

        if result['state'] == 'player_blackjack':
            won, payout = game.get_payout('player_blackjack', self.bet)
            d_val = game.calculate_hand_value(result['dealer_hand'])
            if d_val == 21:
                res = 'push'
                payout = self.bet
                self.cog.wallet.add_balance(self.user.id, payout)
                won = False
            else:
                self.cog.wallet.add_balance(self.user.id, payout)
                res = 'blackjack'
            self.cog.stats.record_game(self.user.id, 'blackjack', self.bet, won, payout)
            self.cog.history.add_result('blackjack', f"#{game_id} {'BLACKJACK' if res == 'blackjack' else 'PUSH'}")

            buf = render_blackjack_hand(result['player_hand'], result['dealer_hand'], hide_dealer=False, result=res)
            file = discord.File(buf, filename="blackjack.png")
            embed = discord.Embed(title=f"🃏 Blackjack #{game_id} - {'BLACKJACK!' if res == 'blackjack' else 'PUSH'}", color=COLOR_WIN if res == 'blackjack' else COLOR_GOLD)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Wager", value=f"{self.bet:,} GP", inline=True)
            embed.add_field(name="Won" if res == 'blackjack' else "Push", value=f"**{payout:,} GP**", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            embed.set_footer(text="Dice & Destiny • Provably Fair")
            await interaction.channel.send(embed=embed, file=file, view=BlackjackResultView(self.user, self.bet, self.cog))
        else:
            buf = render_blackjack_hand(result['player_hand'], result['dealer_hand'], hide_dealer=True)
            file = discord.File(buf, filename="blackjack.png")
            embed = discord.Embed(title=f"🃏 Blackjack #{game_id}", color=COLOR_GOLD)
            embed.add_field(name="Player", value=self.user.mention, inline=True)
            embed.add_field(name="Wager", value=f"{self.bet:,} GP", inline=True)
            embed.add_field(name="Your Hand", value=f"**{result['player_value']}**", inline=True)
            embed.set_image(url="attachment://blackjack.png")
            dealer_shows_ace = result.get('dealer_shows_ace', False)
            embed.set_footer(text="Dealer shows Ace! Insurance available." if dealer_shows_ace else "Hit, Stand, or Double Down!")
            view = BlackjackPlayView(self.user, game, self.bet, game_id, self.cog, dealer_shows_ace=dealer_shows_ace)
            await interaction.channel.send(embed=embed, file=file, view=view)

    @discord.ui.button(label="Verify Fairness", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def verify(self, interaction, button):
        embed = discord.Embed(title="Provably Fair", color=COLOR_GOLD)
        embed.add_field(name="Game", value=f"Blackjack", inline=True)
        embed.set_footer(text="Dice & Destiny")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MinesCashoutView(discord.ui.View):
    """Separate cashout button below the grid"""
    def __init__(self, user, mine_game, bet, cog, grid_msg=None):
        super().__init__(timeout=300)
        self.user = user
        self.mine_game = mine_game
        self.bet = bet
        self.cog = cog
        self.grid_msg = grid_msg

        if mine_game.tiles_revealed > 0 and mine_game.active:
            mult = mine_game._get_multiplier()
            payout = int(bet * mult)
            btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Cashout {payout:,} GP ({mult}x)",
                emoji="💰"
            )
            btn.callback = self._cashout
            self.add_item(btn)

    async def _cashout(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        result = self.mine_game.cashout()
        if not result:
            await interaction.response.send_message("Can't cashout!", ephemeral=True)
            return

        if self.user.id in self.cog.active_mines:
            del self.cog.active_mines[self.user.id]

        self.cog.wallet.add_balance(self.user.id, result['payout'])
        game_id = self.cog.history.next_id()
        self.cog.history.add_result('mines', f"#{game_id} WIN {result['multiplier']}x - {result['tiles_revealed']} tiles")
        self.cog.stats.record_game(self.user.id, 'mines', self.bet, True, result['payout'])

        # Update grid message to show all mines
        if self.grid_msg:
            grid_embed = discord.Embed(title=f"💎 Mines #{game_id} - CASHOUT!", color=COLOR_WIN)
            grid_embed.add_field(name="Player", value=self.user.mention, inline=True)
            grid_embed.add_field(name="Payout", value=f"**{result['payout']:,} GP**", inline=True)
            grid_embed.add_field(name="Profit", value=f"+{result['payout'] - self.bet:,} GP", inline=True)
            final_grid = MinesGridView(self.user, self.mine_game, self.bet, self.cog, game_over=True)
            try:
                await self.grid_msg.edit(embed=grid_embed, view=final_grid)
            except Exception:
                pass

        # Update cashout message
        embed = discord.Embed(title=f"💎 Mines #{game_id} - CASHOUT!", color=COLOR_WIN)
        embed.add_field(name="Wagered", value=f"{self.bet:,} GP", inline=True)
        embed.add_field(name="Multiplier", value=f"{result['multiplier']}x", inline=True)
        embed.add_field(name="Payout", value=f"**{result['payout']:,} GP**", inline=True)
        embed.add_field(name="Tiles", value=str(result['tiles_revealed']), inline=True)
        embed.add_field(name="Profit", value=f"+{result['payout'] - self.bet:,} GP", inline=True)
        seeds = result['seeds']
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        await interaction.response.edit_message(embed=embed, view=None)
        await self.cog.game_logger.log_game(self.user, 'mines', self.bet, True, result['payout'])


class MinesGridView(discord.ui.View):
    """Pure 5x5 grid - 25 tile buttons"""
    def __init__(self, user, mine_game, bet, cog, game_over=False, cashout_msg=None):
        super().__init__(timeout=300)
        self.user = user
        self.mine_game = mine_game
        self.bet = bet
        self.cog = cog
        self.cashout_msg = cashout_msg

        for r in range(5):
            for c in range(5):
                idx = r * 5 + c
                if mine_game.revealed[idx]:
                    if mine_game.grid[idx] == 1:
                        btn = discord.ui.Button(style=discord.ButtonStyle.danger, emoji="💣", row=r, disabled=True)
                    else:
                        btn = discord.ui.Button(style=discord.ButtonStyle.success, emoji="💎", row=r, disabled=True)
                    self.add_item(btn)
                else:
                    if game_over:
                        btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="\u200b", row=r, disabled=True)
                    else:
                        btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="\u200b", row=r)
                        btn.callback = self._make_cb(idx)
                    self.add_item(btn)

    async def _cashout_cb(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        result = self.mine_game.cashout()
        if not result:
            await interaction.response.send_message("Can't cashout!", ephemeral=True)
            return

        if self.user.id in self.cog.active_mines:
            del self.cog.active_mines[self.user.id]

        self.cog.wallet.add_balance(self.user.id, result['payout'])
        game_id = self.cog.history.next_id()
        self.cog.history.add_result('mines', f"#{game_id} WIN {result['multiplier']}x - {result['tiles_revealed']} tiles")
        self.cog.stats.record_game(self.user.id, 'mines', self.bet, True, result['payout'])

        embed = discord.Embed(title=f"💎 Mines #{game_id} - CASHOUT!", color=COLOR_WIN)
        embed.add_field(name="Player", value=self.user.mention, inline=True)
        embed.add_field(name="Wagered", value=f"{self.bet:,} GP", inline=True)
        embed.add_field(name="Tiles", value=str(result['tiles_revealed']), inline=True)
        embed.add_field(name="Multiplier", value=f"{result['multiplier']}x", inline=True)
        embed.add_field(name="Payout", value=f"**{result['payout']:,} GP**", inline=True)
        embed.add_field(name="Profit", value=f"+{result['payout'] - self.bet:,} GP", inline=True)
        seeds = result['seeds']
        embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

        final_view = MinesGridView(self.user, self.mine_game, self.bet, self.cog, game_over=True)
        await interaction.response.edit_message(embed=embed, view=final_view)
        await self.cog.game_logger.log_game(self.user, 'mines', self.bet, True, result['payout'])

    def _make_cb(self, idx):
        async def cb(interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("Not your game!", ephemeral=True)
                return
            result = self.mine_game.reveal_tile(idx)
            if not result:
                await interaction.response.send_message("Invalid!", ephemeral=True)
                return

            if result['hit_mine']:
                if self.user.id in self.cog.active_mines:
                    del self.cog.active_mines[self.user.id]
                game_id = self.cog.history.next_id()
                self.cog.history.add_result('mines', f"#{game_id} LOSS - {self.mine_game.tiles_revealed} tiles")
                self.cog.stats.record_game(self.user.id, 'mines', self.bet, False, 0)

                embed = discord.Embed(title=f"💣 Mines #{game_id} - BOOM!", color=COLOR_LOSS)
                embed.add_field(name="Player", value=self.user.mention, inline=True)
                embed.add_field(name="Lost", value=f"{self.bet:,} GP", inline=True)
                embed.add_field(name="Tiles", value=str(self.mine_game.tiles_revealed), inline=True)
                seeds = result['seeds']
                embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")

                final_view = MinesGridView(self.user, self.mine_game, self.bet, self.cog, game_over=True)
                await interaction.response.edit_message(embed=embed, view=final_view)

                # Remove cashout message
                if self.cashout_msg:
                    try:
                        loss_embed = discord.Embed(title=f"💣 Mines #{game_id} - BOOM!", description=f"Lost {self.bet:,} GP", color=COLOR_LOSS)
                        await self.cashout_msg.edit(embed=loss_embed, view=None)
                    except Exception:
                        pass

                await self.cog.game_logger.log_game(self.user, 'mines', self.bet, False, 0)
            else:
                mult = self.mine_game._get_multiplier()
                potential = int(self.bet * mult)
                embed = discord.Embed(title="💎 MINES", color=COLOR_GOLD)
                embed.add_field(name="Player", value=self.user.mention, inline=True)
                embed.add_field(name="Wager", value=f"{self.bet:,} GP", inline=True)
                embed.add_field(name="Mines", value=str(self.mine_game.mine_count), inline=True)
                embed.add_field(name="Tiles", value=str(self.mine_game.tiles_revealed), inline=True)
                embed.add_field(name="Multiplier", value=f"{mult}x", inline=True)
                embed.add_field(name="Payout", value=f"{potential:,} GP", inline=True)
                embed.set_footer(text="Click tiles or cashout below!")

                new_view = MinesGridView(self.user, self.mine_game, self.bet, self.cog, cashout_msg=self.cashout_msg)
                await interaction.response.edit_message(embed=embed, view=new_view)

                # Update cashout button with new amount
                if self.cashout_msg:
                    try:
                        co_embed = discord.Embed(title="💰 Ready to cashout?", color=COLOR_GOLD)
                        co_embed.add_field(name="Payout", value=f"**{potential:,} GP**", inline=True)
                        co_embed.add_field(name="Multiplier", value=f"{mult}x", inline=True)
                        co_view = MinesCashoutView(self.user, self.mine_game, self.bet, self.cog, grid_msg=interaction.message)
                        await self.cashout_msg.edit(embed=co_embed, view=co_view)
                    except Exception:
                        pass
        return cb


async def setup(bot, config, wallet, wager_tracker, stats, cooldowns, hist, game_logger):
    """Add the game commands cog to the bot"""
    cog = GameCommands(bot, config, wallet, wager_tracker, stats, cooldowns, hist, game_logger)
    await bot.add_cog(cog)
