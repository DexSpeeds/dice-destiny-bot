"""
Dice & Destiny - Discord Casino Bot
Slash command based - all games via /commands
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import asyncio

from permissions import PermissionSystem
from cooldowns import CooldownManager
from stats_tracker import StatsTracker
from game_logger import GameLogger
from wallet_system import WalletSystem
from wager_tracker import WagerTracker
from lottery_system import LotterySystem, TICKET_PRICE
from board_manager import BoardManager
from game_history import GameHistory
from lottery_renderer import render_ticket, render_lottery_background, render_lottery_winners
from leaderboard_renderer import render_leaderboard
from community_roulette import CommunityRoulette, CommunityBetView, setup_community_table, spin_community_roulette, update_community_table, set_community_ref
from referral_system import ReferralSystem, REFERRAL_BONUS

# Colors
COLOR_WIN = 0x2ECC71
COLOR_LOSS = 0xE74C3C
COLOR_GOLD = 0xFFD700

# Load config - from file or example
import os
config_path = 'config.json'
if not os.path.exists(config_path):
    config_path = 'config.example.json'
with open(config_path, 'r') as f:
    config = json.load(f)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Systems
permissions = PermissionSystem()
cooldowns = CooldownManager(cooldown_seconds=3)
stats = StatsTracker()
wallet = WalletSystem()
wager_tracker = WagerTracker()
lottery = LotterySystem()
board_manager = BoardManager(bot)
history = GameHistory()
game_logger = None
community_roulette = None
referrals = ReferralSystem()


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


# ============================================================
# LOTTERY VIEWS + BACKGROUND TASK
# ============================================================

GENERAL_CHANNEL_ID = 1494118573692682251
LOTTERY_CHANNEL_ID = 1499139729549955183


class LotteryBuyView(discord.ui.View):
    """Persistent buy ticket button in lottery channel"""
    def __init__(self):
        super().__init__(timeout=None)  # Persistent!

    @discord.ui.button(label="Buy Ticket (10M GP)", style=discord.ButtonStyle.success,
                       emoji="🎫", custom_id="lottery_buy_ticket")
    async def buy(self, interaction, button):
        user = interaction.user

        if not wallet.has_balance(user.id, TICKET_PRICE):
            bal = wallet.get_balance(user.id)
            await interaction.response.send_message(
                f"Insufficient balance! Need: {TICKET_PRICE:,} GP, Have: {bal:,} GP",
                ephemeral=True
            )
            return

        # Defer immediately to avoid timeout
        await interaction.response.defer(ephemeral=True)

        wallet.remove_balance(user.id, TICKET_PRICE)
        wager_tracker.record_wager(user.id, TICKET_PRICE)

        entry = lottery.buy_ticket(user.id, user.name)
        ticket_no = entry['ticket_no']
        numbers = entry['numbers']

        # Generate ticket image
        buf = render_ticket(user.name, ticket_no, numbers)

        # DM the ticket image
        dm_sent = False
        try:
            file = discord.File(buf, filename=f"ticket_{ticket_no}.png")
            embed = discord.Embed(title=f"🎫 Lottery Ticket #{ticket_no}", color=COLOR_GOLD)
            embed.add_field(name="Numbers", value=" ".join(str(n) for n in numbers), inline=False)
            embed.add_field(name="Draw In", value=lottery.get_time_left(), inline=True)
            embed.set_image(url=f"attachment://ticket_{ticket_no}.png")
            embed.set_footer(text="Good luck! • Dice & Destiny")
            await user.send(embed=embed, file=file)
            dm_sent = True
        except Exception:
            pass

        msg = f"🎫 Ticket #{ticket_no} purchased!"
        if dm_sent:
            msg += " Check your DMs!"
        else:
            msg += f" Numbers: {' '.join(str(n) for n in numbers)}"

        await interaction.followup.send(msg, ephemeral=True)

        # Update the lottery embed in channel
        await update_lottery_embed(interaction.channel)


_lottery_msg = None

async def update_lottery_embed(channel):
    """Update the single lottery message with background image"""
    global _lottery_msg
    status = lottery.get_status()

    # Build player list
    player_counts = {}
    for entry in lottery.entries:
        uid = entry['user_id']
        name = entry['user_name']
        if uid not in player_counts:
            player_counts[uid] = {'name': name, 'tickets': 0}
        player_counts[uid]['tickets'] += 1

    players = list(player_counts.values())
    players.sort(key=lambda p: -p['tickets'])

    # Render background image with big text
    buf = render_lottery_background(
        total_pot=f"Prize Pool: {status['pot_after_edge']:,} GP",
        time_left=f"Next Draw: {status['time_left']}",
        total_entries=f"{status['total_entries']} entries"
    )
    file = discord.File(buf, filename="lottery.png")

    # Build player list for embed
    embed = discord.Embed(color=COLOR_GOLD)
    embed.set_image(url="attachment://lottery.png")

    if players:
        if len(players) <= 10:
            player_text = " | ".join(f"**{p['name']}** ({p['tickets']})" for p in players)
        else:
            top = " | ".join(f"**{p['name']}** ({p['tickets']})" for p in players[:8])
            player_text = f"{top}\n... and {len(players) - 8} more players"
        embed.description = f"🎫 **Entries:** {player_text}"
    else:
        embed.description = "🎫 No entries yet - be the first!"

    # Edit existing message or send new
    if _lottery_msg:
        try:
            await _lottery_msg.edit(embed=embed, view=LotteryBuyView(), attachments=[file])
            return
        except Exception:
            _lottery_msg = None

    async for msg in channel.history(limit=10):
        if msg.author == channel.guild.me:
            try:
                await msg.edit(embed=embed, view=LotteryBuyView(), attachments=[file])
                _lottery_msg = msg
                return
            except Exception:
                pass

    _lottery_msg = await channel.send(embed=embed, file=file, view=LotteryBuyView())


@tasks.loop(seconds=30)
async def lottery_check():
    """Background task: check lottery announcements and draws"""
    if not bot.is_ready():
        return

    # 1 minute warning
    if lottery.should_announce():
        lottery.mark_announced()
        general = bot.get_channel(GENERAL_CHANNEL_ID)
        lottery_ch = bot.get_channel(LOTTERY_CHANNEL_ID)
        if general:
            embed = discord.Embed(
                title="🎫 LOTTERY DRAW IN 1 MINUTE!",
                description=f"**{lottery.get_status()['total_entries']}** tickets in the pot!\n"
                            f"Prize pool: **{lottery.get_status()['pot_after_edge']:,} GP**\n\n"
                            f"Last chance to buy tickets!",
                color=COLOR_GOLD
            )
            if lottery_ch:
                embed.add_field(name="Buy Tickets", value=f"<#{LOTTERY_CHANNEL_ID}>", inline=False)
            await general.send(embed=embed)

    # Draw time
    if lottery.is_draw_time():
        result = lottery.draw()
        if result:
            await perform_lottery_draw(result)


async def perform_lottery_draw(result):
    """Announce lottery results"""
    lottery_ch = bot.get_channel(LOTTERY_CHANNEL_ID)
    results_ch = bot.get_channel(config['channels'].get('game_results', 0))
    general_ch = bot.get_channel(GENERAL_CHANNEL_ID)

    winning_nums = " ".join(f"**{n}**" for n in result['winning_numbers'])

    # Build results embed
    embed = discord.Embed(
        title="🎫 LOTTERY DRAW RESULTS!",
        description=f"**Winning Numbers:** {winning_nums}",
        color=COLOR_WIN
    )
    embed.add_field(name="Total Entries", value=str(result['total_entries']), inline=True)
    embed.add_field(name="Prize Pool", value=f"{result['pot_after_edge']:,} GP", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    for w in result['winners']:
        medal = ["🥇", "🥈", "🥉"][w['place'] - 1]
        embed.add_field(
            name=f"{medal} {w['place']}{'st' if w['place']==1 else 'nd' if w['place']==2 else 'rd'} Place",
            value=f"**{w['user_name']}**\n{w['matches']} matches\n**{w['prize']:,} GP**",
            inline=True
        )

        # Pay winners
        wallet.add_balance(w['user_id'], w['prize'])

        # DM winners
        try:
            user = await bot.fetch_user(w['user_id'])
            dm_embed = discord.Embed(
                title=f"{medal} You won the Dice & Destiny Lottery!",
                description=f"**{w['prize']:,} GP** has been added to your balance!",
                color=COLOR_WIN
            )
            dm_embed.add_field(name="Place", value=f"{w['place']}{'st' if w['place']==1 else 'nd' if w['place']==2 else 'rd'}", inline=True)
            dm_embed.add_field(name="Matches", value=str(w['matches']), inline=True)
            await user.send(embed=dm_embed)
        except Exception:
            pass

    embed.set_footer(text="Next draw in 24 hours! • Dice & Destiny")

    # Render winners podium image
    winners_buf = render_lottery_winners(result['winners'])
    winners_file = discord.File(winners_buf, filename="lottery_winners.png")

    winners_embed = discord.Embed(color=COLOR_WIN)
    winners_embed.set_image(url="attachment://lottery_winners.png")

    # Post to lottery channel
    if lottery_ch:
        await lottery_ch.send(embed=embed)
        await lottery_ch.send(embed=winners_embed, file=winners_file)
        await update_lottery_embed(lottery_ch)

    # Post to results channel
    if results_ch:
        winners_buf2 = render_lottery_winners(result['winners'])
        winners_file2 = discord.File(winners_buf2, filename="lottery_winners.png")
        await results_ch.send(embed=embed)
        await results_ch.send(file=winners_file2)

    # Post to general
    if general_ch:
        winner_text = ", ".join(f"**{w['user_name']}** ({w['prize']:,} GP)" for w in result['winners'])
        announce = discord.Embed(
            title="🎫 LOTTERY WINNERS!",
            description=f"Congratulations to our winners!\n\n{winner_text}",
            color=COLOR_WIN
        )
        announce.add_field(name="Next Draw", value=f"<#{LOTTERY_CHANNEL_ID}> - Buy your tickets now!", inline=False)
        await general_ch.send(embed=announce)


# ============================================================
# BOT EVENTS
# ============================================================

_cog_loaded = False

@bot.event
async def on_ready():
    global game_logger, _cog_loaded
    print("=" * 60)
    print(f"Dice & Destiny - {bot.user.name} ONLINE!")
    print("=" * 60)

    game_logger = GameLogger(bot, config['channels'].get('game_results', 0))

    # Register persistent views
    bot.add_view(LotteryBuyView())

    # Setup lottery - clean old messages and post fresh
    lottery_ch = bot.get_channel(LOTTERY_CHANNEL_ID)
    if lottery_ch:
        try:
            # Remove old embed-only messages (text embeds from before)
            async for msg in lottery_ch.history(limit=20):
                if msg.author == bot.user and msg.embeds and not msg.attachments:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
            await update_lottery_embed(lottery_ch)
        except Exception as e:
            print(f"Lottery embed error: {e}")

    # Start lottery background task
    if not lottery_check.is_running():
        lottery_check.start()

    # Community roulette
    global community_roulette
    if community_roulette is None:
        community_roulette = CommunityRoulette(bot, config, wallet, wager_tracker, stats, history, game_logger)
        set_community_ref(community_roulette)

    # Register persistent views
    bot.add_view(CommunityBetView())
    bot.add_view(ReferralClaimView())

    if not community_roulette_check.is_running():
        community_roulette_check.start()

    if not leaderboard_refresh.is_running():
        leaderboard_refresh.start()

    if not house_stats_refresh.is_running():
        house_stats_refresh.start()

    # Load game commands cog (only once)
    if not _cog_loaded:
        try:
            import game_commands
            await game_commands.setup(bot, config, wallet, wager_tracker, stats, cooldowns, history, game_logger)
            _cog_loaded = True
            print("Game commands cog loaded")
        except Exception as e:
            print(f"ERROR loading cog: {e}")
            import traceback
            traceback.print_exc()

        try:
            # Print all registered commands
            all_cmds = bot.tree.get_commands()
            print(f"Registered commands ({len(all_cmds)}):")
            for cmd in all_cmds:
                print(f"  /{cmd.name}")

            # Clear old guild commands first, then sync fresh
            for guild in bot.guilds:
                bot.tree.clear_commands(guild=guild)
                bot.tree.copy_global_to(guild=guild)
                guild_synced = await bot.tree.sync(guild=guild)
                print(f"Synced {len(guild_synced)} commands to {guild.name}")
            # Also sync globally
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global commands")
        except Exception as e:
            print(f"Sync error: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 60)
    print("READY! Games: /coinflip /blackjack /dice /hotcold")
    print("       /caskets /flowerpoker /roulette /99x")
    print("       /diceduel /mines /cashout")
    print("Admin: /addbalance /setup /leaderboard")
    print("User:  /balance /stats /withdraw")
    print("=" * 60)


# ============================================================
# ============================================================
# HOUSE STATS
# ============================================================

HOUSE_STATS_CHANNEL_ID = 1500121698513457192
_house_stats_msg = None

@bot.tree.command(name="housestats", description="Show house profit/loss stats in this channel")
async def housestats(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    await _update_house_stats(interaction.channel)
    await interaction.followup.send("House stats posted!", ephemeral=True)


async def _update_house_stats(channel=None):
    """Update house stats static message"""
    global _house_stats_msg

    total_wagered = 0
    total_won = 0
    total_lost = 0
    total_players = 0
    total_games = 0

    for uid, s in stats.stats.items():
        total_wagered += s.get('total_wagered', 0)
        total_won += s.get('total_won', 0)
        total_lost += s.get('total_lost', 0)
        total_games += s.get('games_played', 0)
        if s.get('games_played', 0) > 0:
            total_players += 1

    house_profit = total_lost - total_won
    profit_emoji = "📈" if house_profit >= 0 else "📉"

    embed = discord.Embed(
        title="🏦 HOUSE STATISTICS",
        color=COLOR_WIN if house_profit >= 0 else COLOR_LOSS
    )
    embed.add_field(name="Total Wagered", value=f"**{total_wagered:,} GP**", inline=True)
    embed.add_field(name="Total Paid Out", value=f"**{total_won:,} GP**", inline=True)
    embed.add_field(name="Total Collected", value=f"**{total_lost:,} GP**", inline=True)
    embed.add_field(name=f"{profit_emoji} House Profit", value=f"**{house_profit:,} GP**", inline=True)
    embed.add_field(name="Total Players", value=f"**{total_players}**", inline=True)
    embed.add_field(name="Total Games", value=f"**{total_games:,}**", inline=True)

    if total_wagered > 0:
        edge = (house_profit / total_wagered) * 100
        embed.add_field(name="Effective House Edge", value=f"**{edge:.2f}%**", inline=True)

    embed.set_footer(text="Dice & Destiny • Updates every 5 minutes")

    if not channel:
        return

    # Update existing or send new
    if _house_stats_msg:
        try:
            await _house_stats_msg.edit(embed=embed)
            return
        except Exception:
            _house_stats_msg = None

    async for msg in channel.history(limit=10):
        if msg.author == channel.guild.me and msg.embeds:
            for e in msg.embeds:
                if e.title and "HOUSE" in e.title:
                    await msg.edit(embed=embed)
                    _house_stats_msg = msg
                    return

    _house_stats_msg = await channel.send(embed=embed)


@tasks.loop(minutes=5)
async def house_stats_refresh():
    """Auto-refresh house stats in the hardcoded channel"""
    if not bot.is_ready():
        return
    try:
        ch = bot.get_channel(HOUSE_STATS_CHANNEL_ID)
        if ch:
            await _update_house_stats(ch)
    except Exception:
        pass


# ============================================================
# REFERRAL SYSTEM
# ============================================================

class ReferralClaimView(discord.ui.View):
    """Persistent claim button in referral channel"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Referral Code", style=discord.ButtonStyle.success,
                       emoji="🎁", custom_id="referral_claim")
    async def claim(self, interaction, button):
        # Check if already referred
        if referrals.get_referrer(interaction.user.id):
            await interaction.response.send_message("You already claimed a referral code!", ephemeral=True)
            return
        await interaction.response.send_modal(ReferralClaimModal())


class ReferralClaimModal(discord.ui.Modal, title="Enter Referral Code"):
    def __init__(self):
        super().__init__()
        self.code_input = discord.ui.TextInput(
            label="Referral Code", placeholder="chase", required=True, max_length=30
        )
        self.add_item(self.code_input)

    async def on_submit(self, interaction):
        code = self.code_input.value
        success, msg, referrer_id = referrals.claim_code(code, interaction.user.id)

        if not success:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        # Give bonus GP
        wallet.add_balance(interaction.user.id, REFERRAL_BONUS)

        await interaction.response.send_message(
            f"🎁 {msg}\n**{REFERRAL_BONUS:,} GP** added to your balance!",
            ephemeral=True
        )

        # DM the referrer
        try:
            referrer = await interaction.client.fetch_user(referrer_id)
            await referrer.send(
                f"🎉 **{interaction.user.name}** used your referral code! "
                f"You'll earn 10% of house edge on all their bets."
            )
        except Exception:
            pass


@bot.tree.command(name="makecode", description="Create a referral code for a user")
@app_commands.describe(code="The referral code name")
async def makecode(interaction: discord.Interaction, code: str):
    if not await permissions.check_admin_permission(interaction):
        return

    success, msg = referrals.create_code(code, interaction.user.id)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="makecodefor", description="Create a referral code for another user")
@app_commands.describe(user="The user who owns the code", code="The referral code name")
async def makecodefor(interaction: discord.Interaction, user: discord.Member, code: str):
    if not await permissions.check_admin_permission(interaction):
        return

    success, msg = referrals.create_code(code, user.id)
    if success:
        await interaction.response.send_message(f"Code **{code}** created for {user.mention}!", ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="refstats", description="View referral stats")
async def refstats(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return

    codes = referrals.get_all_codes()
    if not codes:
        await interaction.response.send_message("No referral codes yet.", ephemeral=True)
        return

    embed = discord.Embed(title="🎁 Referral Stats", color=COLOR_GOLD)
    for c in codes:
        try:
            u = await bot.fetch_user(c['owner_id'])
            name = u.name
        except Exception:
            name = f"User {c['owner_id']}"
        embed.add_field(
            name=f"Code: {c['code']}",
            value=f"Owner: **{name}**\nUsed: {c['used_count']}x\nEarned: {c['total_earned']:,} GP",
            inline=True
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="openreferrals", description="Setup the referral channel with claim button")
async def openreferrals(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    channel = interaction.channel

    # Clear old messages
    async for msg in channel.history(limit=20):
        if msg.author == bot.user:
            try:
                await msg.delete()
            except Exception:
                pass

    # Post referral image with claim button
    import os
    img_path = os.path.join(os.path.dirname(__file__), 'assets', 'referral.png')
    file = discord.File(img_path, filename="referral.png")

    embed = discord.Embed(color=COLOR_GOLD)
    embed.set_image(url="attachment://referral.png")

    view = ReferralClaimView()
    await channel.send(embed=embed, file=file, view=view)

    await interaction.followup.send("Referral channel setup!", ephemeral=True)


# ============================================================
# COMMUNITY ROULETTE TIMER
@tasks.loop(seconds=10)
async def community_roulette_check():
    """Check if community roulette round should spin"""
    if not bot.is_ready() or community_roulette is None:
        return
    if community_roulette.is_spinning or community_roulette.table_msg is None:
        return

    # Update table timer
    if community_roulette.get_bet_count() > 0:
        try:
            await update_community_table(community_roulette)
        except Exception:
            pass

    # Check if round time is up
    import time as _time
    if _time.time() >= community_roulette.round_end and community_roulette.get_bet_count() > 0:
        await spin_community_roulette(community_roulette)


@bot.tree.command(name="openroulette", description="Open the community roulette table")
async def open_roulette(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer()
    await setup_community_table(community_roulette, interaction.channel)
    await interaction.followup.send("Community roulette table opened!", ephemeral=True)


@bot.tree.command(name="spin", description="Force spin the community roulette")
async def force_spin(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    if community_roulette.get_bet_count() == 0:
        await interaction.response.send_message("No bets placed!", ephemeral=True)
        return
    await interaction.response.defer()
    await spin_community_roulette(community_roulette)
    await interaction.followup.send("Spin complete!", ephemeral=True)


# ============================================================
# ADMIN COMMANDS
# ============================================================

@bot.tree.command(name="addbalance")
@app_commands.describe(user="User", amount="Amount (e.g. 100k, 1m, 1b)")
async def addbalance(interaction: discord.Interaction, user: discord.Member, amount: str):
    if not await permissions.check_admin_permission(interaction):
        return

    parsed = parse_bet(amount)
    if parsed <= 0:
        await interaction.response.send_message(f"Invalid amount: `{amount}`", ephemeral=True)
        return

    wallet.add_balance(user.id, parsed)
    wager_tracker.record_deposit(user.id, parsed)

    embed = discord.Embed(title="Balance Added", color=COLOR_GOLD)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Added", value=f"{parsed:,} GP")
    embed.add_field(name="New Balance", value=f"{wallet.get_balance(user.id):,} GP")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):
    bal = wallet.get_balance(interaction.user.id)
    embed = discord.Embed(title="Balance", description=f"**{bal:,} GP**", color=COLOR_GOLD)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="stats")
async def stats_cmd(interaction: discord.Interaction):
    user_stats = stats.get_user_stats(interaction.user.id)
    win_rate = stats.get_win_rate(interaction.user.id)
    profit = stats.get_profit(interaction.user.id)

    embed = discord.Embed(title=f"Stats - {interaction.user.name}", color=COLOR_GOLD)
    embed.add_field(name="Games", value=f"{user_stats['games_played']:,}", inline=True)
    embed.add_field(name="Won", value=f"{user_stats['games_won']:,}", inline=True)
    embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
    embed.add_field(name="Wagered", value=f"{user_stats['total_wagered']:,} GP", inline=True)
    embed.add_field(name="Total Won", value=f"{user_stats['total_won']:,} GP", inline=True)
    p_emoji = "+" if profit >= 0 else ""
    embed.add_field(name="Profit", value=f"{p_emoji}{profit:,} GP", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="withdraw")
@app_commands.describe(amount="Amount (e.g. 100k, 1m, 1b)")
async def withdraw(interaction: discord.Interaction, amount: str):
    withdraw_amount = parse_bet(amount)
    if withdraw_amount <= 0:
        await interaction.response.send_message(f"Invalid: `{amount}`", ephemeral=True)
        return

    bal = wallet.get_balance(interaction.user.id)
    if withdraw_amount > bal:
        await interaction.response.send_message(f"Insufficient! Balance: {bal:,} GP", ephemeral=True)
        return

    progress = wager_tracker.get_wager_progress(interaction.user.id)
    if not progress['can_withdraw']:
        await interaction.response.send_message(
            f"Wager requirement not met!\n"
            f"Required: {progress['required']:,} GP\n"
            f"Completed: {progress['completed']:,} GP ({progress['percentage']:.1f}%)\n"
            f"Remaining: {progress['remaining']:,} GP",
            ephemeral=True
        )
        return

    ch = bot.get_channel(config['channels'].get('game_results', 0))
    if ch:
        embed = discord.Embed(title="WITHDRAWAL REQUEST", color=COLOR_GOLD)
        embed.add_field(name="User", value=interaction.user.mention)
        embed.add_field(name="Amount", value=f"{withdraw_amount:,} GP")
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)
    await interaction.response.send_message(f"Withdrawal submitted! Amount: {withdraw_amount:,} GP", ephemeral=True)


_leaderboard_msg = None


async def _update_leaderboard():
    """Render and update the leaderboard image"""
    global _leaderboard_msg

    # Get top 10 by wagered
    all_players = []
    for user_id, s in stats.stats.items():
        all_players.append((int(user_id), s))
    all_players.sort(key=lambda x: x[1].get('total_wagered', 0), reverse=True)
    top10 = all_players[:10]

    # Build player list with names
    players = []
    for uid, s in top10:
        try:
            u = await bot.fetch_user(uid)
            name = u.name
        except Exception:
            name = f"User {uid}"
        players.append({'name': name, 'wagered': s.get('total_wagered', 0)})

    # Render image
    buf = render_leaderboard(players)
    file = discord.File(buf, filename="leaderboard.png")

    ch = bot.get_channel(config['channels'].get('leaderboard', 0))
    if not ch:
        return

    # Update existing or send new
    if _leaderboard_msg:
        try:
            await _leaderboard_msg.edit(attachments=[file])
            return
        except Exception:
            _leaderboard_msg = None

    async for msg in ch.history(limit=10):
        if msg.author == bot.user:
            try:
                await msg.edit(attachments=[file])
                _leaderboard_msg = msg
                return
            except Exception:
                pass

    _leaderboard_msg = await ch.send(file=file)


@tasks.loop(minutes=3)
async def leaderboard_refresh():
    """Auto-refresh leaderboard every hour"""
    if not bot.is_ready():
        return
    try:
        await _update_leaderboard()
    except Exception as e:
        print(f"Leaderboard refresh error: {e}")


@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        await _update_leaderboard()
        await interaction.followup.send("Leaderboard updated!", ephemeral=True)
    except Exception as e:
        print(f"Leaderboard error: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(f"Error: {e}", ephemeral=True)


# ============================================================
# SETUP - Create channels with info embeds
# ============================================================

@bot.tree.command(name="renamechannels", description="Add emoji icons to all game channel names")
async def renamechannels(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    channel_names = {
        'lottery': '🎫-lottery',
        'coinflip': '🪙-coinflip',
        'blackjack': '🃏-blackjack',
        'dice': '🎲-dice',
        'hotcold': '🌸-hot-cold',
        'caskets': '📦-caskets',
        'flowerpoker': '🌺-flower-poker',
        'roulette': '🎰-roulette',
        'mines': '💎-mines',
        'ninetynine': '🍀-99x',
        'diceduel': '⚔️-dice-duel',
        'game-results': '📊-game-results',
        'leaderboard': '🏆-leaderboard',
        'community-roulette': '🎰-community-roulette',
    }

    renamed = 0
    for ch_id_str, game_name in config['channels'].get('game_channels', {}).items():
        new_name = channel_names.get(game_name)
        if not new_name:
            continue
        ch = bot.get_channel(int(ch_id_str))
        if ch and ch.name != new_name:
            try:
                await ch.edit(name=new_name)
                renamed += 1
                await asyncio.sleep(2)  # Rate limit
            except Exception as e:
                print(f"Failed to rename {game_name}: {e}")

    # Also rename results and leaderboard
    for key, new_name in [('game_results', '📊-game-results'), ('leaderboard', '🏆-leaderboard')]:
        ch_id = config['channels'].get(key)
        if ch_id:
            ch = bot.get_channel(ch_id)
            if ch and ch.name != new_name:
                try:
                    await ch.edit(name=new_name)
                    renamed += 1
                    await asyncio.sleep(2)
                except Exception:
                    pass

    await interaction.followup.send(f"Renamed {renamed} channels!", ephemeral=True)


@bot.tree.command(name="uploademojis", description="Upload game icons as server emojis")
async def uploademojis(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    import os
    emoji_dir = os.path.join(os.path.dirname(__file__), 'assets', 'emojis')
    guild = interaction.guild
    uploaded = 0
    skipped = 0

    for filename in os.listdir(emoji_dir):
        if not filename.endswith('.png'):
            continue
        name = filename[:-4]  # Remove .png

        # Check if emoji already exists
        existing = discord.utils.get(guild.emojis, name=name)
        if existing:
            skipped += 1
            continue

        filepath = os.path.join(emoji_dir, filename)
        with open(filepath, 'rb') as f:
            image_data = f.read()

        try:
            await guild.create_custom_emoji(name=name, image=image_data)
            uploaded += 1
            await asyncio.sleep(1)  # Rate limit
        except Exception as e:
            print(f"Failed to upload {name}: {e}")

    await interaction.followup.send(
        f"Uploaded {uploaded} emojis, {skipped} already existed.",
        ephemeral=True
    )


@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    if not await permissions.check_admin_permission(interaction):
        return

    await interaction.response.send_message("Setting up channels...", ephemeral=True)
    guild = interaction.guild

    # Find or create category
    category = None
    cat_id = config['channels'].get('category_id')
    if cat_id:
        ch = bot.get_channel(cat_id)
        if isinstance(ch, discord.CategoryChannel):
            category = ch
    if not category:
        category = discord.utils.get(guild.categories, name="Dice & Destiny")
        if not category:
            category = await guild.create_category("Dice & Destiny")
        config['channels']['category_id'] = category.id

    # Game info for setup embeds
    game_info = {
        'coinflip': {'title': '🪙 COINFLIP', 'desc': '`/coinflip <heads/tails> <bet>`\nPayout: **1.9x**'},
        'blackjack': {'title': '🃏 BLACKJACK', 'desc': '`/blackjack <bet>`\nWin: **1.9x** | Blackjack: **2.5x**'},
        'dice': {'title': '🎲 DICE', 'desc': '`/dice <under/mid/over> <bet>`\nUnder (1-26): **3.6x** | Mid (27-74): **1.9x** | Over (75-100): **3.6x**'},
        'hotcold': {'title': '🌸 HOT / COLD', 'desc': '`/hotcold <color> <bet>`\nHot: **2x** | Cold: **2.1x** | Color: **6x**\nBlack: **400x** | White: **800x**'},
        'caskets': {'title': '📦 CASKETS', 'desc': '`/caskets <tier> <bet>`\nCoin: **1.9x** | Gem: **2.5x** | Rare: **5x**'},
        'flowerpoker': {'title': '🌸 FLOWER POKER', 'desc': '`/flowerpoker <player/host/draw> <bet>`\nPlayer/Host: **1.9x** | Draw: **2.8x**'},
        'roulette': {'title': '🎰 ROULETTE', 'desc': '`/roulette <choice> <bet>`\nRed/Black: **1.9x** | Dozens: **2x**'},
        'mines': {'title': '💎 MINES', 'desc': '`/mines <mine_count> <bet>`\nReveal tiles, avoid mines! `/cashout` to collect'},
        'ninetynine': {'title': '🍀 99x', 'desc': '`/99x <number> <bet>`\nPick 1-100, match = **99x** payout!'},
        'diceduel': {'title': '🎲 DICE DUEL', 'desc': '`/diceduel <bet>`\nYou vs House - highest roll wins! **1.9x**'},
        'lottery': {'title': '🎫 LOTTERY', 'desc': 'Coming soon...'},
    }

    game_order = ['coinflip', 'blackjack', 'dice', 'hotcold', 'caskets', 'flowerpoker', 'roulette', 'mines', 'ninetynine', 'diceduel']
    extra = ['game-results', 'leaderboard']

    created = 0
    for game_name in game_order:
        try:
            existing = discord.utils.get(category.channels, name=game_name)
            if existing:
                channel = existing
            else:
                channel = await category.create_text_channel(game_name)
                created += 1
                await asyncio.sleep(1)

            config['channels']['game_channels'][str(channel.id)] = game_name

            async for msg in channel.history(limit=50):
                if msg.author == bot.user:
                    await msg.delete()

            info = game_info.get(game_name, {'title': game_name.upper(), 'desc': 'Play!'})
            embed = discord.Embed(
                title=info['title'],
                description=info['desc'] + "\n\n**Bet Format:** 100k, 1m, 5m",
                color=COLOR_GOLD
            )
            gs = config['game_settings'].get(game_name, {})
            if 'min_bet' in gs:
                embed.add_field(name="Min", value=f"{gs['min_bet']:,} GP", inline=True)
                embed.add_field(name="Max", value=f"{gs['max_bet']:,} GP", inline=True)
            embed.set_footer(text="Dice & Destiny • Provably Fair")
            await channel.send(embed=embed)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Setup error {game_name}: {e}")

    for ch_name in extra:
        try:
            existing = discord.utils.get(category.channels, name=ch_name)
            if not existing:
                ch = await category.create_text_channel(ch_name)
                created += 1
                await asyncio.sleep(1)
            else:
                ch = existing
            if ch_name == 'game-results':
                config['channels']['game_results'] = ch.id
            elif ch_name == 'leaderboard':
                config['channels']['leaderboard'] = ch.id
        except Exception as e:
            print(f"Setup error {ch_name}: {e}")

    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass  # On Railway, config.json may not be writable

    await interaction.followup.send(f"Done! Created {created} channels. All games ready via /commands.", ephemeral=True)


# ============================================================
# RUN
# ============================================================

# Global error handler - print all command errors
@bot.tree.error
async def on_app_command_error(interaction, error):
    print(f"COMMAND ERROR: {error}")
    import traceback
    traceback.print_exc()
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error: {error}", ephemeral=True)
    except Exception:
        pass

# Token from environment variable (for deployment) or config (for local dev)
import os
bot_token = os.environ.get('BOT_TOKEN') or config.get('bot_token')
if not bot_token:
    print("ERROR: No bot token! Set BOT_TOKEN environment variable or add to config.json")
    exit(1)
bot.run(bot_token)
