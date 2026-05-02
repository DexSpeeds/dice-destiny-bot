"""
Permission System - Owner + Cashier for admin, everyone can play
"""
import discord
import json
import os

_config_path = 'config.json' if os.path.exists('config.json') else 'config.example.json'
with open(_config_path, 'r') as f:
    _config = json.load(f)

OWNER_IDS = _config['staff']['owner_ids']
CASHIER_ROLE_ID = _config['staff'].get('cashier_role_id', 0)


class PermissionSystem:
    """Handle all permission checks"""

    @staticmethod
    async def check_play_permission(interaction: discord.Interaction) -> bool:
        """Everyone can play"""
        return True

    @staticmethod
    async def check_admin_permission(interaction: discord.Interaction) -> bool:
        """Owner, Cashier role, or Discord admin"""
        member = interaction.user

        # Server owner
        if member.id == interaction.guild.owner_id:
            return True

        # Hardcoded owner IDs
        if member.id in OWNER_IDS:
            return True

        # Cashier role
        if CASHIER_ROLE_ID and any(role.id == CASHIER_ROLE_ID for role in member.roles):
            return True

        # Discord admin permission
        if member.guild_permissions.administrator:
            return True

        await interaction.response.send_message(
            "You don't have permission for this command.",
            ephemeral=True
        )
        return False
