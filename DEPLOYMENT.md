# NotaryTON Deployment Guide

Complete guide to deploy your TON memecoin auto-notarization bot to Render.com with custom domain.

---

## ⚠️ BEFORE YOU START

### 1. Fix Wallet Issue (CRITICAL)

Your wallet needs TON before the bot can work:

```bash
# Check your wallet balance
open https://tonscan.org/address/UQA7fe14R2mFavSOI_oiIVp4lcEo-lypybpIiLD2OmazZpY7
```

**If balance is 0:**
1. Open Telegram → @wallet
2. Send → Paste: `UQA7fe14R2mFavSOI_oiIVp4lcEo-lypybpIiLD2OmazZpY7`
3. Amount: 0.5 TON (or more)
4. Wait 1-2 minutes → Check tonscan.org again

**You MUST have TON in your wallet before deploying!**

---

## 📋 Prerequisites

- [x] GitHub account
- [x] Render.com account (free tier)
- [x] GoDaddy domain: `notaryton.com`
- [x] TON wallet with funds
- [x] All `.env` variables ready

---

## 🚀 PART 1: Deploy to Render.com

### Step 1: Push Code to GitHub

```bash
cd /home/jesse/dev/projects/personal/ton/notaryton-bot

# Initialize git if not already done
git init
git add .
git commit -m "Initial commit - NotaryTON memecoin auto-notary bot"

# Create repo on GitHub (via browser or gh CLI)
gh repo create notaryton-bot --public --source=. --remote=origin --push

# Or manually:
# 1. Go to github.com/new
# 2. Name: notaryton-bot
# 3. Public
# 4. Don't initialize with README
# 5. Copy the git remote add command and run it
# 6. git push -u origin main
```

### Step 2: Create Render Web Service

1. **Go to [render.com/dashboard](https://dashboard.render.com/)**

2. **Click "New +" → "Web Service"**

3. **Connect GitHub**:
   - Click "Connect account" (if not connected)
   - Select your `notaryton-bot` repository

4. **Configure Service**:
   - **Name**: `notaryton-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Plan**: Free

5. **Add Environment Variables**:
   Click "Advanced" → "Add Environment Variable" for each:

   ```
   BOT_TOKEN=8513443424:AAHKhpZOJJL9QVDHr-3dgYzdpw_JOMvHUJc
   TON_CENTER_API_KEY=05a0e608459eb273fe48f502a2c8bd5df3894db4cdd250bffa7e3a6b37bf5550
   TON_WALLET_SECRET=sign frequent wing picnic material slush present mammal grit remind cricket pulse oxygen velvet jeans train risk trigger glory just velvet aspect walnut shield
   SERVICE_TON_WALLET=UQA7fe14R2mFavSOI_oiIVp4lcEo-lypybpIiLD2OmazZpY7
   WEBHOOK_URL=https://notaryton.onrender.com
   GROUP_IDS=
   ```

   ⚠️ **IMPORTANT**:
   - Use your actual values from `.env`
   - `WEBHOOK_URL` will be `https://notaryton.onrender.com` (Render auto-assigns this)
   - Leave `GROUP_IDS` empty for now (add group chat IDs later)

6. **Click "Create Web Service"**

7. **Wait for deployment** (~5 minutes):
   - Render will:
     - Clone your repo
     - Install dependencies
     - Start the bot
     - Set webhook automatically

8. **Verify deployment**:
   - Check logs for: `✅ Webhook set to: https://notaryton.onrender.com/webhook/...`
   - Visit: `https://notaryton.onrender.com/` → Should see `{"status":"running"}`

---

## 🌐 PART 2: Configure GoDaddy Domain

### Step 1: Get Render IP/CNAME

Render provides a URL like `https://notaryton.onrender.com`. You need to point your domain to it.

1. **In Render Dashboard**:
   - Click your `notaryton-bot` service
   - Go to "Settings" → "Custom Domains"
   - Click "Add Custom Domain"
   - Enter: `notaryton.com`
   - Render will show you DNS instructions

### Step 2: Configure DNS in GoDaddy

1. **Log in to [GoDaddy DNS Management](https://dcc.godaddy.com/)**

2. **Find `notaryton.com` → Click "DNS"**

3. **Add CNAME Record**:
   - Click "Add Record"
   - **Type**: CNAME
   - **Name**: `@` (or `www` if you want `www.notaryton.com`)
   - **Value**: `notaryton.onrender.com` (from Render)
   - **TTL**: 600 seconds
   - **Save**

4. **Wait 5-60 minutes** for DNS propagation

### Step 3: Update Webhook URL

Once DNS is live:

1. **In Render → Environment Variables**:
   - Change `WEBHOOK_URL` from `https://notaryton.onrender.com` → `https://notaryton.com`
   - Save

2. **Restart the service**:
   - Render → "Manual Deploy" → "Deploy latest commit"

3. **Verify**:
   - Visit `https://notaryton.com/` → Should see `{"status":"running"}`
   - Bot will auto-update webhook to `https://notaryton.com/webhook/...`

---

## ✅ PART 3: Test the Bot

### 1. Test Basic Commands

Open Telegram → Find `@NotaryTON_bot`:

```
/start
```

Should see welcome message with commands.

```
/status
```

Should see "No Active Subscription" (normal - you haven't subscribed yet).

### 2. Test File Notarization

**First, you need to subscribe or pay:**

```
/subscribe
```

Follow instructions to send 0.1 TON to your wallet.

**Then send any file** → Bot should seal it and return hash + tonscan link.

### 3. Test Group Monitoring

1. **Create a test group** in Telegram
2. **Add @NotaryTON_bot** to the group
3. **Make it admin** (so it can read messages)
4. **Get the group chat ID**:
   - Send a message in the group
   - Check bot logs in Render for the chat ID
   - Or use `@getidsbot` in the group

5. **Add to `.env` / Render env vars**:
   ```
   GROUP_IDS=-1001234567890
   ```

6. **Restart bot** → It will join the group

7. **Test auto-notarization**:
   - Post a message like: `"New launch! tx: ABC123XYZ"`
   - Bot should detect it (if from a deploy bot username)

---

## 🔧 PART 4: Run Admin Outreach Campaign

Once the bot is working:

```bash
# On your local machine
cd /home/jesse/dev/projects/personal/ton/notaryton-bot

python outreach.py
```

This will:
- Find admins in TON-related groups
- DM them about NotaryTON
- Offer 5% referral commission
- Log all sent DMs to `outreach_sent.csv`

**Rate limits**:
- 1 second between DMs
- 3 seconds between groups
- Automatically skips already-contacted admins

---

## 📊 Monitoring & Logs

### View Render Logs

```bash
# In Render Dashboard → your service → "Logs"
# Or via CLI:
render logs -s notaryton-bot --tail
```

Look for:
- `✅ Webhook set to: ...`
- `✅ Joined group: ...`
- `✅ Auto-Notarized!`
- `Error` messages (fix immediately)

### Check Stats

Visit: `https://notaryton.com/stats`

Returns:
```json
{
  "total_users": 42,
  "total_notarizations": 127
}
```

---

## 🐛 Troubleshooting

### Bot Not Responding

1. **Check Render logs** for errors
2. **Verify webhook**:
   ```bash
   curl https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
   ```
   Should show: `"url": "https://notaryton.com/webhook/..."`

3. **Test health endpoint**:
   ```bash
   curl https://notaryton.com/
   ```
   Should return: `{"status":"running"}`

### "Contract Not Initialized" Error

Your wallet has 0 TON. **Transfer TON first** (see top of this guide).

### Group Not Joining

1. **Bot must be admin** in the group
2. **Privacy mode must be disabled**:
   - @BotFather → `/mybots` → your bot → "Bot Settings" → "Group Privacy" → "Turn off"

### Payments Not Activating

Payment polling runs automatically every 30 seconds with retry logic. If payments aren't activating:

1. **Check logs** for Liteserver errors (will auto-retry with exponential backoff)
2. **Verify memo format** - user must include their Telegram user ID as the memo
3. **Check wallet balance** - bot wallet needs TON to send notarization txs

To manually activate a subscription (emergency only):
```python
# In Python shell
import asyncio
from bot import add_subscription
asyncio.run(add_subscription(user_id=123456789, months=1))
```

---

## 💰 Next Steps

1. ✅ **Deploy to Render** (you're here)
2. ✅ **Configure domain**
3. 🔄 **Test thoroughly**
4. 📢 **Run outreach campaign**
5. 💎 **Implement full payment verification**
6. 🚀 **Scale to 100+ groups**
7. 📈 **Track metrics & optimize**

---

## 🆘 Need Help?

- **Render logs**: Check for errors first
- **Test locally**: Run with ngrok before deploying
- **Wallet issues**: Check tonscan.org for balance
- **Domain issues**: Wait 1 hour for DNS propagation

**You're building something HUGE. Let's ship it! 🚀**
