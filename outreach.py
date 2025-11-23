import asyncio
import csv
import os
from datetime import datetime
from aiogram import Bot
from dotenv import load_dotenv

# Load .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

# Target groups (add more as needed)
TARGET_GROUPS = [
    "@tonpumps",
    "@defitoncalls",
    "@toncommunity",
    "@tonmemes",
    "@tondaoofficial",
    # Add more group usernames here
]

# DM template
DM_TEMPLATE = """Yo {admin_name},

@NotaryTON_bot auto-notarizes launches for 0.001 TON—bulletproof against FUD/rugs.

Want to pin it by your deploy bot? You snag 5% cut per use (tracked via referral codes).

Test here: https://t.me/NotaryTON_bot

Reply "interested" and I'll set you up with your referral link.

Cheers! 🔐"""

# Track sent DMs to avoid duplicates
SENT_LOG = "outreach_sent.csv"

def load_sent_log():
    """Load list of already contacted admins"""
    if not os.path.exists(SENT_LOG):
        return set()

    sent = set()
    with open(SENT_LOG, 'r') as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header
        for row in reader:
            if row:
                sent.add(row[0])
    return sent

def log_sent_dm(admin_id, admin_name, group):
    """Log a sent DM"""
    with open(SENT_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        if os.stat(SENT_LOG).st_size == 0:
            writer.writerow(["admin_id", "admin_name", "group", "timestamp"])
        writer.writerow([admin_id, admin_name, group, datetime.now().isoformat()])

async def get_group_admins(group_username):
    """Get list of admins for a group"""
    try:
        # Try to get chat by username
        chat = await bot.get_chat(group_username)
        chat_id = chat.id

        # Get administrators
        admins = await bot.get_chat_administrators(chat_id)

        return [(admin.user.id, admin.user.first_name, admin.user.username) for admin in admins if not admin.user.is_bot]
    except Exception as e:
        print(f"❌ Failed to get admins for {group_username}: {e}")
        return []

async def send_dm_to_admin(admin_id, admin_name, group):
    """Send DM to an admin"""
    sent_log = load_sent_log()

    if str(admin_id) in sent_log:
        print(f"⏭️  Skipping {admin_name} (already contacted)")
        return False

    try:
        message = DM_TEMPLATE.format(admin_name=admin_name)
        await bot.send_message(admin_id, message)

        log_sent_dm(admin_id, admin_name, group)
        print(f"✅ Sent DM to {admin_name} ({admin_id}) from {group}")
        return True
    except Exception as e:
        print(f"❌ Failed to DM {admin_name} ({admin_id}): {e}")
        return False

async def run_outreach():
    """Main outreach loop"""
    print("🚀 Starting NotaryTON Admin Outreach Campaign\n")

    total_sent = 0
    total_failed = 0
    total_skipped = 0

    for group in TARGET_GROUPS:
        print(f"\n📢 Processing group: {group}")

        admins = await get_group_admins(group)

        if not admins:
            print(f"   No admins found or group inaccessible")
            continue

        print(f"   Found {len(admins)} admins")

        for admin_id, admin_name, admin_username in admins:
            result = await send_dm_to_admin(admin_id, admin_name, group)

            if result:
                total_sent += 1
            elif result is False:
                total_failed += 1
            else:
                total_skipped += 1

            # Rate limit: 1 second between DMs
            await asyncio.sleep(1)

        # Longer pause between groups
        await asyncio.sleep(3)

    print(f"\n\n📊 Campaign Summary:")
    print(f"   ✅ Sent: {total_sent}")
    print(f"   ❌ Failed: {total_failed}")
    print(f"   ⏭️  Skipped: {total_skipped}")
    print(f"\n📋 Full log saved to: {SENT_LOG}")

async def main():
    """Entry point"""
    try:
        await run_outreach()
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
