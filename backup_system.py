"""
Backup System - Auto-saves data files to GitHub
Runs every 10 minutes to push wallets, stats, etc.
"""
import os
import subprocess
import shutil
from datetime import datetime

DATA_FILES = [
    'wallets.json',
    'player_stats.json',
    'game_history.json',
    'wager_tracker.json',
    'lottery_data.json',
    'referral_data.json',
]

BACKUP_DIR = 'backups'


def create_local_backup():
    """Create a timestamped local backup"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    for f in DATA_FILES:
        if os.path.exists(f):
            backup_name = f"{BACKUP_DIR}/{timestamp}_{f}"
            shutil.copy2(f, backup_name)

    # Keep only last 10 backups per file
    all_backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    if len(all_backups) > 60:  # 10 backups * 6 files
        for old in all_backups[60:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except Exception:
                pass


async def push_to_github():
    """Push data files to GitHub for persistent backup"""
    try:
        # Check if git is available
        result = subprocess.run(['git', 'status', '--porcelain'],
                              capture_output=True, text=True, timeout=10)

        if not result.stdout.strip():
            return False  # Nothing to commit

        # Stage data files
        for f in DATA_FILES:
            if os.path.exists(f):
                subprocess.run(['git', 'add', f], capture_output=True, timeout=10)

        # Commit
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        subprocess.run(
            ['git', 'commit', '-m', f'Auto-backup data {timestamp}'],
            capture_output=True, timeout=10
        )

        # Push
        result = subprocess.run(
            ['git', 'push'],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            print(f"Backup pushed to GitHub: {timestamp}")
            return True
        else:
            print(f"Backup push failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"Backup error: {e}")
        return False
