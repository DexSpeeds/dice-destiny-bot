"""
Community Roulette - Live table where multiple players bet on the same spin
"""
import discord
from discord.ext import tasks
from discord import app_commands
import asyncio
import time
import json

from roulette_renderer import render_roulette_gif, _get_table, _paste_disk, _draw_chip, _fill_fields, _number_color, _draw_rolling_ball, _get_font, CHIP_POSITIONS, WHEEL_ORDER, NUM_SLOTS
from PIL import Image, ImageDraw, ImageFont
import io
import math

COLOR_WIN = 0x2ECC71
COLOR_LOSS = 0xE74C3C
COLOR_GOLD = 0xFFD700

# Chip colors per player (cycle through these)
PLAYER_COLORS = [
    (220, 40, 40),    # Red
    (40, 120, 220),   # Blue
    (40, 200, 80),    # Green
    (200, 160, 40),   # Gold
    (180, 40, 200),   # Purple
    (40, 200, 200),   # Cyan
    (220, 120, 40),   # Orange
    (200, 60, 120),   # Pink
]

ROUND_DURATION = 60  # seconds per round


class CommunityRoulette:
    """Manages the community roulette game state"""

    def __init__(self, bot, config, wallet, wager_tracker, stats, history, game_logger):
        self.bot = bot
        self.config = config
        self.wallet = wallet
        self.wager_tracker = wager_tracker
        self.stats = stats
        self.history = history
        self.game_logger = game_logger

        self.bets = {}  # {user_id: [{choice, amount, user_name}]}
        self.round_end = 0
        self.channel_id = None
        self.table_msg = None      # Post 1: the table
        self.results_msg = None    # Post 2: last round results
        self.is_spinning = False
        self.player_colors = {}
        self.color_idx = 0
        self.last_results = []     # Store results for display

    def get_player_color(self, user_id):
        if user_id not in self.player_colors:
            self.player_colors[user_id] = PLAYER_COLORS[self.color_idx % len(PLAYER_COLORS)]
            self.color_idx += 1
        return self.player_colors[user_id]

    def place_bet(self, user_id, user_name, choice, amount):
        """Place a bet for the current round"""
        if user_id not in self.bets:
            self.bets[user_id] = []
        self.bets[user_id].append({
            'choice': choice,
            'amount': amount,
            'user_name': user_name,
        })

    def get_total_bets(self):
        total = 0
        for uid, user_bets in self.bets.items():
            for bet in user_bets:
                total += bet['amount']
        return total

    def get_bet_count(self):
        count = 0
        for uid, user_bets in self.bets.items():
            count += len(user_bets)
        return count

    def get_player_count(self):
        return len(self.bets)

    def get_time_left(self):
        remaining = self.round_end - time.time()
        if remaining <= 0:
            return "Spinning!"
        return f"{int(remaining)}s"

    def start_round(self):
        self.bets = {}
        self.round_end = time.time() + ROUND_DURATION
        self.is_spinning = False
        self.player_colors = {}
        self.color_idx = 0

    def render_table_with_bets(self):
        """Render the table showing all placed bets as chips"""
        from roulette_renderer import _get_table, _get_font
        img = _get_table()
        draw = ImageDraw.Draw(img)
        font = _get_font(14)
        small = _get_font(11)

        # Draw chips for each bet
        for user_id, user_bets in self.bets.items():
            color = self.get_player_color(user_id)
            for bet in user_bets:
                pos = CHIP_POSITIONS.get(bet['choice'])
                if bet['choice'].startswith('number_'):
                    num = int(bet['choice'].split('_')[1])
                    from roulette_renderer import _get_number_pos
                    pos = _get_number_pos(num)
                if not pos:
                    continue

                cx, cy = pos
                # Offset slightly so multiple chips don't overlap perfectly
                offset_x = (hash(user_id) % 5 - 2) * 8
                offset_y = (hash(user_id + 1000) % 5 - 2) * 8
                cx += offset_x
                cy += offset_y

                # Draw chip
                chip_r = 20
                draw.ellipse([(cx - chip_r, cy - chip_r), (cx + chip_r, cy + chip_r)],
                             fill=color, outline=(255, 215, 0), width=3)
                draw.ellipse([(cx - chip_r + 5, cy - chip_r + 5), (cx + chip_r - 5, cy + chip_r - 5)],
                             outline=(255, 215, 0, 150), width=1)

                # Amount
                if bet['amount'] >= 1_000_000:
                    text = f"{bet['amount'] // 1_000_000}M"
                elif bet['amount'] >= 1_000:
                    text = f"{bet['amount'] // 1_000}K"
                else:
                    text = str(bet['amount'])
                bbox = draw.textbbox((0, 0), text, font=small)
                tw = bbox[2] - bbox[0]
                draw.text((cx - tw // 2, cy - 6), text, fill=(255, 255, 255), font=small)

                # Player name above chip
                name = bet['user_name'][:10]
                bbox2 = draw.textbbox((0, 0), name, font=small)
                tw2 = bbox2[2] - bbox2[0]
                draw.text((cx - tw2 // 2, cy - chip_r - 15), name, fill=color, font=small)

        # Timer in the wheel frame
        time_left = self.get_time_left()
        timer_font = _get_font(32)
        draw.text((790, 250), time_left, fill=(255, 215, 0), font=timer_font, anchor="mm")

        # Info text
        info_font = _get_font(18)
        draw.text((835, 200), f"{self.get_player_count()} players | {self.get_bet_count()} bets",
                  fill=(200, 200, 200), font=info_font, anchor="mm")
        draw.text((835, 290), f"Pot: {self.get_total_bets():,} GP",
                  fill=(255, 215, 0), font=info_font, anchor="mm")

        buf = io.BytesIO()
        img.convert('RGB').save(buf, format='PNG')
        buf.seek(0)
        return buf


# Global reference so persistent view can access it
_community_ref = None


def set_community_ref(community):
    global _community_ref
    _community_ref = community


class CommunityBetView(discord.ui.View):
    """Persistent bet buttons for community roulette"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Red 2x", style=discord.ButtonStyle.danger, emoji="🔴", row=0, custom_id="cr_red")
    async def red(self, interaction, button):
        await self._bet(interaction, 'red')

    @discord.ui.button(label="Black 2x", style=discord.ButtonStyle.secondary, emoji="⚫", row=0, custom_id="cr_black")
    async def black(self, interaction, button):
        await self._bet(interaction, 'black')

    @discord.ui.button(label="Even 2x", style=discord.ButtonStyle.primary, emoji="2️⃣", row=0, custom_id="cr_even")
    async def even(self, interaction, button):
        await self._bet(interaction, 'even')

    @discord.ui.button(label="Odd 2x", style=discord.ButtonStyle.primary, emoji="1️⃣", row=0, custom_id="cr_odd")
    async def odd(self, interaction, button):
        await self._bet(interaction, 'odd')

    @discord.ui.button(label="1-18", style=discord.ButtonStyle.success, emoji="⬇️", row=1, custom_id="cr_low")
    async def low(self, interaction, button):
        await self._bet(interaction, 'low')

    @discord.ui.button(label="19-36", style=discord.ButtonStyle.success, emoji="⬆️", row=1, custom_id="cr_high")
    async def high(self, interaction, button):
        await self._bet(interaction, 'high')

    @discord.ui.button(label="1st12 3x", style=discord.ButtonStyle.secondary, emoji="1️⃣", row=1, custom_id="cr_dozen1")
    async def dozen1(self, interaction, button):
        await self._bet(interaction, 'dozen1')

    @discord.ui.button(label="2nd12 3x", style=discord.ButtonStyle.secondary, emoji="2️⃣", row=1, custom_id="cr_dozen2")
    async def dozen2(self, interaction, button):
        await self._bet(interaction, 'dozen2')

    @discord.ui.button(label="3rd12 3x", style=discord.ButtonStyle.secondary, emoji="3️⃣", row=1, custom_id="cr_dozen3")
    async def dozen3(self, interaction, button):
        await self._bet(interaction, 'dozen3')

    @discord.ui.button(label="Number 35x", style=discord.ButtonStyle.primary, emoji="🎯", row=2, custom_id="cr_number")
    async def number(self, interaction, button):
        if not _community_ref or _community_ref.is_spinning:
            await interaction.response.send_message("Wheel is spinning! Wait for next round.", ephemeral=True)
            return
        await interaction.response.send_modal(
            CommunityNumberModal(_community_ref, interaction.user)
        )

    async def _bet(self, interaction, choice):
        if not _community_ref or _community_ref.is_spinning:
            await interaction.response.send_message("Wheel is spinning! Wait for next round.", ephemeral=True)
            return
        await interaction.response.send_modal(
            CommunityBetModal(_community_ref, interaction.user, choice)
        )


class CommunityBetModal(discord.ui.Modal, title="Place your bet"):
    def __init__(self, community, user, choice):
        super().__init__()
        self.community = community
        self.user = user
        self.choice = choice
        self.bet_input = discord.ui.TextInput(
            label=f"Bet amount on {choice.upper()}", placeholder="100k, 1m, 5m", required=True
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction):
        from game_commands import parse_bet
        amount = parse_bet(self.bet_input.value)
        if amount <= 0:
            await interaction.response.send_message("Invalid amount!", ephemeral=True)
            return
        if not self.community.wallet.has_balance(self.user.id, amount):
            await interaction.response.send_message("Insufficient balance!", ephemeral=True)
            return

        self.community.wallet.remove_balance(self.user.id, amount)
        self.community.wager_tracker.record_wager(self.user.id, amount)
        self.community.place_bet(self.user.id, self.user.name, self.choice, amount)

        await interaction.response.send_message(
            f"🎰 Bet placed! **{amount:,} GP** on **{self.choice.upper()}**",
            ephemeral=True
        )

        # Update table image
        await update_community_table(self.community)


class CommunityNumberModal(discord.ui.Modal, title="Pick a Number (0-36)"):
    def __init__(self, community, user):
        super().__init__()
        self.community = community
        self.user = user
        self.number_input = discord.ui.TextInput(
            label="Number (0-36)", placeholder="e.g. 17", required=True, max_length=2
        )
        self.bet_input = discord.ui.TextInput(
            label="Bet amount", placeholder="100k, 1m, 5m", required=True
        )
        self.add_item(self.number_input)
        self.add_item(self.bet_input)

    async def on_submit(self, interaction):
        from game_commands import parse_bet
        try:
            number = int(self.number_input.value)
        except ValueError:
            await interaction.response.send_message("Invalid number!", ephemeral=True)
            return
        if number < 0 or number > 36:
            await interaction.response.send_message("Must be 0-36!", ephemeral=True)
            return

        amount = parse_bet(self.bet_input.value)
        if amount <= 0:
            await interaction.response.send_message("Invalid amount!", ephemeral=True)
            return
        if not self.community.wallet.has_balance(self.user.id, amount):
            await interaction.response.send_message("Insufficient balance!", ephemeral=True)
            return

        self.community.wallet.remove_balance(self.user.id, amount)
        self.community.wager_tracker.record_wager(self.user.id, amount)
        self.community.place_bet(self.user.id, self.user.name, f'number_{number}', amount)

        await interaction.response.send_message(
            f"🎯 Bet placed! **{amount:,} GP** on **Number {number}** (35x)",
            ephemeral=True
        )
        await update_community_table(self.community)


async def update_community_table(community):
    """Update the table image in the channel"""
    if not community.table_msg:
        return

    buf = community.render_table_with_bets()
    file = discord.File(buf, filename="community_roulette.png")

    try:
        await community.table_msg.edit(attachments=[file])
    except Exception:
        pass


async def spin_community_roulette(community):
    """Perform the community spin and resolve all bets"""
    community.is_spinning = True
    channel = community.bot.get_channel(community.channel_id)
    if not channel:
        return

    from games.roulette import Roulette
    roulette = Roulette()
    result = roulette.play(0, 'red')
    winning_number = result['number']
    color = result['color']
    seeds = result.get('seeds', {})

    game_id = community.history.next_id()
    ce = "🔴" if color == 'red' else "⚫" if color == 'black' else "🟢"

    # Resolve all bets + send ephemeral DMs
    results_text = []
    for user_id, user_bets in community.bets.items():
        total_won = 0
        total_bet = 0
        for bet in user_bets:
            amount = bet['amount']
            choice = bet['choice']
            total_bet += amount

            if choice.startswith('number_'):
                num = int(choice.split('_')[1])
                won = winning_number == num
                payout = int(amount * 35) if won else 0
            else:
                check_result = roulette.check_bet(winning_number, choice)
                won = check_result[0]
                payout = int(amount * check_result[1]) if won else 0

            if won:
                community.wallet.add_balance(user_id, payout)
                total_won += payout

            community.stats.record_game(user_id, 'roulette', amount, won, payout)

        profit = total_won - total_bet
        name = user_bets[0]['user_name']
        if profit > 0:
            results_text.append(f"✅ **{name}** | Bet: {total_bet:,} GP | Won: +{profit:,} GP")
        elif profit == 0 and total_won > 0:
            results_text.append(f"🤝 **{name}** | Bet: {total_bet:,} GP | Break even")
        else:
            results_text.append(f"❌ **{name}** | Bet: {total_bet:,} GP | Lost")

        # No DMs - results go to game-results channel

    community.history.add_result('roulette', f"#{game_id} {ce}{winning_number} COMMUNITY")
    community.last_results = results_text

    # Update Post 1: table with spinning GIF
    gif_buf = render_roulette_gif(
        game_id=game_id, bettor="Community", chip=community.get_total_bets(),
        bet_type='red', winning_number=winning_number,
        won=False, payout=0, recent_results=[]
    )
    file = discord.File(gif_buf, filename="spin.gif")

    if community.table_msg:
        try:
            await community.table_msg.edit(view=None, attachments=[file])
        except Exception:
            pass

    # Update Post 2: results in channel
    if community.results_msg:
        results_embed = discord.Embed(
            title=f"🏆 Round #{game_id} Results - {ce} {winning_number} ({color.upper()})",
            description="\n".join(results_text) if results_text else "No bets this round.",
            color=COLOR_GOLD
        )
        # Provably fair
        seed_hash = seeds.get('server_seed_hash', 'N/A')
        results_embed.add_field(
            name="Provably Fair",
            value=f"Server seed: `{seed_hash[:32]}...`\nClient seed: `{seeds.get('client_seed', 'N/A')}`\nNonce: `{seeds.get('nonce', 'N/A')}`",
            inline=False
        )
        try:
            await community.results_msg.edit(embed=results_embed)
        except Exception:
            pass

    # Also post to game-results channel
    results_ch_id = community.config['channels'].get('game_results', 0)
    results_ch = community.bot.get_channel(results_ch_id)
    if results_ch and results_text:
        gr_embed = discord.Embed(
            title=f"🎰 Community Roulette #{game_id} - {ce} {winning_number} ({color.upper()})",
            description="\n".join(results_text),
            color=COLOR_GOLD
        )
        gr_embed.set_footer(text=f"Server seed: {seeds.get('server_seed_hash', 'N/A')[:32]}...")
        try:
            await results_ch.send(embed=gr_embed)
        except Exception:
            pass

    # Wait, then reset for new round
    await asyncio.sleep(8)
    community.start_round()
    community.is_spinning = False

    # Reset Post 1 with fresh table + buttons
    buf = community.render_table_with_bets()
    new_file = discord.File(buf, filename="community_roulette.png")

    view = CommunityBetView()
    if community.table_msg:
        try:
            await community.table_msg.edit(view=view, attachments=[new_file])
        except Exception:
            pass


async def setup_community_table(community, channel):
    """Post 2 static messages: table + results, lock channel, create chat thread"""
    community.start_round()
    community.channel_id = channel.id

    # Clear old bot messages
    async for msg in channel.history(limit=30):
        if msg.author == channel.guild.me:
            try:
                await msg.delete()
            except Exception:
                pass

    # Lock channel - only bot can send messages, players use buttons
    try:
        everyone = channel.guild.default_role
        await channel.set_permissions(everyone, send_messages=False, use_application_commands=True)
        await channel.set_permissions(channel.guild.me, send_messages=True)
    except Exception as e:
        print(f"Could not lock channel: {e}")

    # Post 1: The table with buttons
    buf = community.render_table_with_bets()
    file = discord.File(buf, filename="community_roulette.png")

    view = CommunityBetView()
    community.table_msg = await channel.send(file=file, view=view)

    # Create chat thread attached to the table message
    try:
        thread = await community.table_msg.create_thread(name="Open Chat 💬")
        await thread.send("Chat here while you play! 🎰")
        community.chat_thread = thread
    except Exception as e:
        print(f"Could not create thread: {e}")
        community.chat_thread = None

    # Post 2: Results (starts empty)
    results_embed = discord.Embed(
        title="🏆 Last Round Results",
        description="No results yet. Waiting for first spin...",
        color=COLOR_GOLD
    )
    community.results_msg = await channel.send(embed=results_embed)
