"""
Game Results Logger - Post to results channel
"""
import discord
from datetime import datetime

# Colors
COLOR_WIN = 0x00FF00
COLOR_LOSS = 0xFF0000

class GameLogger:
    """Log game results to channel"""
    
    def __init__(self, bot, results_channel_id: int):
        self.bot = bot
        self.results_channel_id = results_channel_id
    
    async def log_game(
        self,
        user: discord.Member,
        game_name: str,
        bet: int,
        won: bool,
        payout: int,
        details: dict = None
    ):
        """Log game result"""
        try:
            channel = self.bot.get_channel(self.results_channel_id)
            if not channel:
                return
            
            # Create embed
            color = COLOR_WIN if won else COLOR_LOSS
            result_emoji = "✅" if won else "❌"
            
            embed = discord.Embed(
                title=f"{result_emoji} {game_name.upper()}",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            embed.set_author(
                name=user.name,
                icon_url=user.display_avatar.url if user.display_avatar else None
            )
            
            # Main info
            embed.add_field(
                name="💰 Bet",
                value=f"{bet:,} GP",
                inline=True
            )
            
            if won:
                embed.add_field(
                    name="🎉 Won",
                    value=f"{payout:,} GP",
                    inline=True
                )
                embed.add_field(
                    name="📈 Profit",
                    value=f"+{payout - bet:,} GP",
                    inline=True
                )
            else:
                embed.add_field(
                    name="💸 Lost",
                    value=f"{bet:,} GP",
                    inline=True
                )
            
            # Add game-specific details if provided
            if details:
                for key, value in details.items():
                    embed.add_field(name=key, value=value, inline=True)
            
            embed.set_footer(text="Dice & Destiny • Provably Fair")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error logging game: {e}")
