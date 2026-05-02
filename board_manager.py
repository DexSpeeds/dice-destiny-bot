"""
Board Manager - Live updating game boards
"""
import discord
from datetime import datetime

class BoardManager:
    """Manage live game boards"""
    
    def __init__(self, bot):
        self.bot = bot
        self.boards = {}  # {channel_id: message_id}
    
    async def create_lottery_board(self, channel: discord.TextChannel, lottery_status: dict) -> discord.Message:
        """Create/update lottery board"""
        
        embed = discord.Embed(
            title="🎫 LOTTERY - 24 HOUR DRAW",
            description="Buy tickets and win BIG!",
            color=0xFFD700
        )
        
        # Stats
        embed.add_field(
            name="⏰ Time Until Draw",
            value=lottery_status['time_left'],
            inline=True
        )
        
        embed.add_field(
            name="🎟️ Total Tickets",
            value=f"{lottery_status['total_entries']} entries",
            inline=True
        )
        
        embed.add_field(
            name="💰 Prize Pool",
            value=f"{lottery_status['prize_pool']:,} GP",
            inline=True
        )
        
        # Breakdown
        total_pot = lottery_status['total_pot']
        house_cut = lottery_status['house_cut']
        prize_pool = lottery_status['prize_pool']
        
        breakdown = f"**Total Pot:** {total_pot:,} GP\n"
        breakdown += f"**House Cut (15%):** {house_cut:,} GP\n"
        breakdown += f"**Prize Pool (85%):** {prize_pool:,} GP\n\n"
        breakdown += f"**1st Place:** {int(prize_pool * 0.5):,} GP (50%)\n"
        breakdown += f"**2nd Place:** {int(prize_pool * 0.3):,} GP (30%)\n"
        breakdown += f"**3rd Place:** {int(prize_pool * 0.2):,} GP (20%)"
        
        embed.add_field(
            name="💎 Prize Breakdown",
            value=breakdown,
            inline=False
        )
        
        # Current entries
        if lottery_status['entries']:
            entries_text = ""
            for uid, data in list(lottery_status['entries'].items())[:10]:
                status = "✅" if data.get('confirmed') else "⏳"
                entries_text += f"{status} **{data['username']}** - {data['tickets']} ticket(s)\n"
            
            if len(lottery_status['entries']) > 10:
                entries_text += f"\n*...and {len(lottery_status['entries']) - 10} more*"
            
            embed.add_field(
                name="🎟️ Current Entries",
                value=entries_text or "No entries yet!",
                inline=False
            )
        
        embed.set_footer(text=f"Round #{lottery_status['round_id']} | Updates every minute")
        embed.timestamp = datetime.utcnow()
        
        # Send or update
        if channel.id in self.boards:
            try:
                msg = await channel.fetch_message(self.boards[channel.id])
                await msg.edit(embed=embed)
                return msg
            except:
                pass
        
        # Create new
        msg = await channel.send(embed=embed)
        self.boards[channel.id] = msg.id
        return msg
