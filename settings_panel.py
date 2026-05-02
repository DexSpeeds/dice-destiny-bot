"""
Settings Panel - Admin UI for configuring the bot via Discord
Embed with buttons + modals for all configuration
"""
import discord
from discord import app_commands
import json
import os

COLOR_GOLD = 0xFFD700
CONFIG_PATH = 'config.json'
EXAMPLE_PATH = 'config.example.json'


def _load_config():
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH
    with open(path, 'r') as f:
        return json.load(f)


def _save_config(config):
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def build_settings_embed(config):
    """Build the main settings overview embed"""
    embed = discord.Embed(title="⚙️ DICE & DESTINY SETTINGS", color=COLOR_GOLD)

    # Roles
    owner_ids = config.get('staff', {}).get('owner_ids', [])
    cashier_role = config.get('staff', {}).get('cashier_role_id', 0)
    admin_roles = config.get('staff', {}).get('admin_roles', [])

    roles_text = f"**Owner IDs:** {', '.join(str(i) for i in owner_ids) if owner_ids else 'None'}\n"
    roles_text += f"**Cashier Role:** <@&{cashier_role}>\n" if cashier_role else "**Cashier Role:** Not set\n"
    if admin_roles:
        roles_text += f"**Admin Roles:** {', '.join(f'<@&{r}>' for r in admin_roles)}\n"
    else:
        roles_text += "**Admin Roles:** None\n"
    embed.add_field(name="👥 Roles & Permissions", value=roles_text, inline=False)

    # Game settings
    gs = config.get('game_settings', {})
    games_text = ""
    for game, settings in gs.items():
        if 'max_bet' in settings:
            games_text += f"**{game}:** min {settings.get('min_bet', 0):,} / max {settings['max_bet']:,}\n"
    embed.add_field(name="🎲 Bet Limits", value=games_text[:1024] if games_text else "No games", inline=False)

    # Lottery
    lottery_price = gs.get('lottery', {}).get('min_bet', 50000000)
    embed.add_field(name="🎫 Lottery", value=f"Ticket Price: **{lottery_price:,} GP**", inline=True)

    # House edge
    embed.add_field(name="🏦 House Edge", value="**10%** on all games", inline=True)

    embed.set_footer(text="Click a button below to change settings")
    return embed


class SettingsView(discord.ui.View):
    """Main settings panel buttons"""
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Add Admin Role", style=discord.ButtonStyle.primary, emoji="👑", row=0)
    async def add_admin(self, interaction, button):
        await interaction.response.send_modal(AddAdminRoleModal())

    @discord.ui.button(label="Remove Admin Role", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def remove_admin(self, interaction, button):
        await interaction.response.send_modal(RemoveAdminRoleModal())

    @discord.ui.button(label="Set Cashier Role", style=discord.ButtonStyle.primary, emoji="💰", row=0)
    async def set_cashier(self, interaction, button):
        await interaction.response.send_modal(SetCashierRoleModal())

    @discord.ui.button(label="Set Max Bet", style=discord.ButtonStyle.secondary, emoji="🎲", row=1)
    async def set_max_bet(self, interaction, button):
        await interaction.response.send_modal(SetMaxBetModal())

    @discord.ui.button(label="Set Min Bet", style=discord.ButtonStyle.secondary, emoji="🎲", row=1)
    async def set_min_bet(self, interaction, button):
        await interaction.response.send_modal(SetMinBetModal())

    @discord.ui.button(label="Set Lottery Price", style=discord.ButtonStyle.success, emoji="🎫", row=1)
    async def set_lottery(self, interaction, button):
        await interaction.response.send_modal(SetLotteryPriceModal())

    @discord.ui.button(label="Add Owner ID", style=discord.ButtonStyle.primary, emoji="🔑", row=2)
    async def add_owner(self, interaction, button):
        await interaction.response.send_modal(AddOwnerModal())

    @discord.ui.button(label="View Current Config", style=discord.ButtonStyle.secondary, emoji="📋", row=2)
    async def view_config(self, interaction, button):
        config = _load_config()
        embed = build_settings_embed(config)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AddAdminRoleModal(discord.ui.Modal, title="Add Admin Role"):
    def __init__(self):
        super().__init__()
        self.role_id = discord.ui.TextInput(
            label="Role ID", placeholder="Right-click role → Copy ID", required=True
        )
        self.add_item(self.role_id)

    async def on_submit(self, interaction):
        try:
            role_id = int(self.role_id.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid role ID!", ephemeral=True)
            return

        config = _load_config()
        if 'admin_roles' not in config.get('staff', {}):
            config.setdefault('staff', {})['admin_roles'] = []

        if role_id not in config['staff']['admin_roles']:
            config['staff']['admin_roles'].append(role_id)
            _save_config(config)

            # Update permissions module
            _update_permissions(config)

            await interaction.response.send_message(
                f"✅ Role <@&{role_id}> added as admin!", ephemeral=True
            )
        else:
            await interaction.response.send_message("Role already admin!", ephemeral=True)


class RemoveAdminRoleModal(discord.ui.Modal, title="Remove Admin Role"):
    def __init__(self):
        super().__init__()
        self.role_id = discord.ui.TextInput(
            label="Role ID to remove", placeholder="Right-click role → Copy ID", required=True
        )
        self.add_item(self.role_id)

    async def on_submit(self, interaction):
        try:
            role_id = int(self.role_id.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid role ID!", ephemeral=True)
            return

        config = _load_config()
        admin_roles = config.get('staff', {}).get('admin_roles', [])

        if role_id in admin_roles:
            admin_roles.remove(role_id)
            _save_config(config)
            _update_permissions(config)
            await interaction.response.send_message(
                f"✅ Role <@&{role_id}> removed from admin!", ephemeral=True
            )
        else:
            await interaction.response.send_message("Role not found in admins!", ephemeral=True)


class SetCashierRoleModal(discord.ui.Modal, title="Set Cashier Role"):
    def __init__(self):
        super().__init__()
        self.role_id = discord.ui.TextInput(
            label="Cashier Role ID", placeholder="Right-click role → Copy ID", required=True
        )
        self.add_item(self.role_id)

    async def on_submit(self, interaction):
        try:
            role_id = int(self.role_id.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid role ID!", ephemeral=True)
            return

        config = _load_config()
        config.setdefault('staff', {})['cashier_role_id'] = role_id
        _save_config(config)
        _update_permissions(config)
        await interaction.response.send_message(
            f"✅ Cashier role set to <@&{role_id}>!", ephemeral=True
        )


class SetMaxBetModal(discord.ui.Modal, title="Set Max Bet (all games)"):
    def __init__(self):
        super().__init__()
        self.amount = discord.ui.TextInput(
            label="Max bet amount", placeholder="e.g. 500000000 or 500m", required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        from game_commands import parse_bet
        amount = parse_bet(self.amount.value)
        if amount <= 0:
            await interaction.response.send_message("Invalid amount!", ephemeral=True)
            return

        config = _load_config()
        for game in config.get('game_settings', {}).values():
            if 'max_bet' in game:
                game['max_bet'] = amount
        _save_config(config)
        await interaction.response.send_message(
            f"✅ Max bet set to **{amount:,} GP** for all games!", ephemeral=True
        )


class SetMinBetModal(discord.ui.Modal, title="Set Min Bet (all games)"):
    def __init__(self):
        super().__init__()
        self.amount = discord.ui.TextInput(
            label="Min bet amount", placeholder="e.g. 100000 or 100k", required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        from game_commands import parse_bet
        amount = parse_bet(self.amount.value)
        if amount <= 0:
            await interaction.response.send_message("Invalid amount!", ephemeral=True)
            return

        config = _load_config()
        for game in config.get('game_settings', {}).values():
            if 'min_bet' in game:
                game['min_bet'] = amount
        _save_config(config)
        await interaction.response.send_message(
            f"✅ Min bet set to **{amount:,} GP** for all games!", ephemeral=True
        )


class SetLotteryPriceModal(discord.ui.Modal, title="Set Lottery Ticket Price"):
    def __init__(self):
        super().__init__()
        self.amount = discord.ui.TextInput(
            label="Ticket price", placeholder="e.g. 50000000 or 50m", required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        from game_commands import parse_bet
        amount = parse_bet(self.amount.value)
        if amount <= 0:
            await interaction.response.send_message("Invalid amount!", ephemeral=True)
            return

        config = _load_config()
        config.setdefault('game_settings', {}).setdefault('lottery', {})['min_bet'] = amount
        config['game_settings']['lottery']['max_bet'] = amount
        _save_config(config)

        # Update lottery system
        from lottery_system import LotterySystem
        import lottery_system
        lottery_system.TICKET_PRICE = amount

        await interaction.response.send_message(
            f"✅ Lottery ticket price set to **{amount:,} GP**!", ephemeral=True
        )


class AddOwnerModal(discord.ui.Modal, title="Add Owner ID"):
    def __init__(self):
        super().__init__()
        self.user_id = discord.ui.TextInput(
            label="User ID", placeholder="Right-click user → Copy ID", required=True
        )
        self.add_item(self.user_id)

    async def on_submit(self, interaction):
        try:
            user_id = int(self.user_id.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid user ID!", ephemeral=True)
            return

        config = _load_config()
        owners = config.setdefault('staff', {}).setdefault('owner_ids', [])
        if user_id not in owners:
            owners.append(user_id)
            _save_config(config)
            _update_permissions(config)
            await interaction.response.send_message(
                f"✅ User {user_id} added as owner!", ephemeral=True
            )
        else:
            await interaction.response.send_message("Already an owner!", ephemeral=True)


def _update_permissions(config):
    """Update the permissions module with new config"""
    import permissions
    permissions.OWNER_IDS = config.get('staff', {}).get('owner_ids', [])
    permissions.CASHIER_ROLE_ID = config.get('staff', {}).get('cashier_role_id', 0)
    # Add admin_roles support
    if not hasattr(permissions, 'ADMIN_ROLES'):
        permissions.ADMIN_ROLES = []
    permissions.ADMIN_ROLES = config.get('staff', {}).get('admin_roles', [])
