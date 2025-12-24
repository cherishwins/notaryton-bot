# NotaryTON API Documentation

## Base URL
```
Production: https://notaryton.com
```

## Authentication
Use your Telegram user ID as the API key. Get it via `/api` command in @MemeSealTON_bot.

**Requirements**: Active subscription (15 Stars or 0.3 TON/month)

---

## Endpoints

### 1. Notarize Single Contract

**POST** `/api/v1/notarize`

Notarize a single TON contract with optional metadata.

#### Request Body
```json
{
  "api_key": "123456789",
  "contract_address": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
  "metadata": {
    "project_name": "MyCoin",
    "launch_date": "2025-11-24",
    "description": "Revolutionary memecoin"
  }
}
```

#### Response (Success)
```json
{
  "success": true,
  "hash": "a3f8b92c1e4d5678901234567890abcdef123456789",
  "contract": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
  "timestamp": "2025-11-24T10:30:00.123456",
  "tx_url": "https://tonscan.org/",
  "verify_url": "https://notaryton.com/api/v1/verify/a3f8b92c1e4d5678901234567890abcdef123456789"
}
```

#### Response (Error)
```json
{
  "success": false,
  "error": "No active subscription",
  "subscribe_url": "https://t.me/NotaryTON_bot?start=subscribe"
}
```

#### cURL Example
```bash
curl -X POST https://notaryton.com/api/v1/notarize \
  -H 'Content-Type: application/json' \
  -d '{
    "api_key": "123456789",
    "contract_address": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
    "metadata": {
      "project_name": "MyCoin"
    }
  }'
```

---

### 2. Batch Notarization

**POST** `/api/v1/batch`

Notarize up to 50 contracts in a single request.

#### Request Body
```json
{
  "api_key": "123456789",
  "contracts": [
    {
      "address": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
      "name": "Coin1"
    },
    {
      "address": "EQAnotherContractAddressHere123456789012345",
      "name": "Coin2"
    }
  ]
}
```

#### Response
```json
{
  "success": true,
  "processed": 2,
  "results": [
    {
      "success": true,
      "address": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
      "hash": "a3f8b92c1e4d5678901234567890abcdef123456789",
      "verify_url": "https://notaryton.com/api/v1/verify/a3f8b92c..."
    },
    {
      "success": true,
      "address": "EQAnotherContractAddressHere123456789012345",
      "hash": "b4e9c03d2f5e67890123456789abcdef0123456789",
      "verify_url": "https://notaryton.com/api/v1/verify/b4e9c03..."
    }
  ]
}
```

#### cURL Example
```bash
curl -X POST https://notaryton.com/api/v1/batch \
  -H 'Content-Type: application/json' \
  -d '{
    "api_key": "123456789",
    "contracts": [
      {"address": "EQ...", "name": "Coin1"},
      {"address": "EQ...", "name": "Coin2"}
    ]
  }'
```

---

### 3. Verify Notarization

**GET** `/api/v1/verify/{hash}`

Verify a notarization by its hash. **No authentication required** - public endpoint.

#### Parameters
- `hash` (path): The contract hash to verify

#### Response (Verified)
```json
{
  "verified": true,
  "hash": "a3f8b92c1e4d5678901234567890abcdef123456789",
  "tx_hash": "EQ...",
  "timestamp": "2025-11-24T10:30:00.123456",
  "notarized_by": "NotaryTON",
  "blockchain": "TON",
  "explorer_url": "https://tonscan.org/tx/..."
}
```

#### Response (Not Found)
```json
{
  "verified": false,
  "hash": "a3f8b92c1e4d5678901234567890abcdef123456789",
  "message": "No notarization found for this hash"
}
```

#### cURL Example
```bash
curl https://notaryton.com/api/v1/verify/a3f8b92c1e4d5678901234567890abcdef123456789
```

---

## Rate Limits

- **Free Tier**: Not available (subscription required)
- **Subscription**: 1,000 requests/day
- **Batch Endpoint**: Max 50 contracts per request
- **Verification Endpoint**: Unlimited (public)

---

## Error Codes

| Code | Message | Solution |
|------|---------|----------|
| 400 | Missing api_key or contract_address | Check request body |
| 401 | No active subscription | Subscribe via @MemeSealTON_bot |
| 404 | Contract not found | Verify contract address |
| 429 | Rate limit exceeded | Upgrade plan or wait |
| 500 | Internal server error | Contact support |

---

## Integration Examples

### Python
```python
import requests

API_KEY = "123456789"
BASE_URL = "https://notaryton.com"

def notarize_contract(address, name=""):
    response = requests.post(
        f"{BASE_URL}/api/v1/notarize",
        json={
            "api_key": API_KEY,
            "contract_address": address,
            "metadata": {"project_name": name}
        }
    )
    return response.json()

# Usage
result = notarize_contract("EQ...", "MyCoin")
print(f"Hash: {result['hash']}")
print(f"Verify: {result['verify_url']}")
```

### JavaScript (Node.js)
```javascript
const axios = require('axios');

const API_KEY = '123456789';
const BASE_URL = 'https://notaryton.com';

async function notarizeContract(address, name = '') {
  const response = await axios.post(`${BASE_URL}/api/v1/notarize`, {
    api_key: API_KEY,
    contract_address: address,
    metadata: { project_name: name }
  });
  return response.data;
}

// Usage
notarizeContract('EQ...', 'MyCoin')
  .then(result => {
    console.log(`Hash: ${result.hash}`);
    console.log(`Verify: ${result.verify_url}`);
  });
```

### Telegram Bot Integration
```python
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

@dp.message(Command("verify"))
async def verify_launch(message: types.Message):
    # Extract contract address from message
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Usage: /verify <address>")
        return
    
    address = parts[1]
    
    # Notarize via NotaryTON API
    result = notarize_contract(address)
    
    if result['success']:
        await message.reply(
            f"✅ Verified!\n"
            f"Hash: {result['hash'][:16]}...\n"
            f"Proof: {result['verify_url']}"
        )
    else:
        await message.reply(f"❌ Error: {result['error']}")
```

---

## Use Cases

### 1. Deploy Bot Integration
Automatically notarize every contract you deploy:
```python
async def on_contract_deployed(address):
    # Deploy contract
    tx = await deploy_contract(...)
    
    # Auto-notarize
    result = notarize_contract(address, project_name)
    
    # Share proof with users
    await bot.send_message(chat_id, f"✅ Notarized: {result['verify_url']}")
```

### 2. DEX Pre-Listing Verification
Verify contracts before listing on exchange:
```python
async def verify_before_listing(token_address):
    # Check if already notarized
    response = requests.get(f"{BASE_URL}/api/v1/verify/{token_address}")
    
    if response.json()['verified']:
        # Safe to list
        await list_token(token_address)
    else:
        # Require notarization first
        await notify_user("Please notarize your contract first")
```

### 3. Analytics Dashboard
Track all launches in real-time:
```python
async def monitor_launches():
    # Your bot detects new launch
    contract = detect_new_launch()
    
    # Notarize it
    result = notarize_contract(contract)
    
    # Store in your database
    db.save({
        'contract': contract,
        'hash': result['hash'],
        'timestamp': result['timestamp']
    })
```

---

## Support

- **Telegram**: @MemeSealTON_bot
- **Issues**: [GitHub Issues](https://github.com/cherishwins/notaryton-bot/issues)
- **Docs**: https://notaryton.com/docs

---

---

## Token Intelligence API (MemeScan)

### 4. Rug Score Lookup

**GET** `/score/{address}`

Get safety score and rug analysis for any TON token. **No authentication required.**

#### Parameters
- `address` (path): Token contract address (jetton master)

#### Response
```json
{
  "address": "EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG",
  "symbol": "PEPE",
  "name": "Pepe Token",
  "safety_score": 75,
  "safety_level": "warning",
  "holder_count": 156,
  "top_holder_pct": 23.5,
  "liquidity_usd": 12500.00,
  "rugged": false,
  "first_seen": "2024-12-20T14:30:00Z"
}
```

#### Safety Levels
| Score | Level | Meaning |
|-------|-------|---------|
| 80-100 | `safe` | Low rug risk |
| 50-79 | `warning` | Some concerns |
| 0-49 | `danger` | High rug risk |

#### cURL Example
```bash
curl https://notaryton.com/score/EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG
```

---

### 5. Token Stats (Dashboard)

**GET** `/api/v1/tokens/stats`

Get aggregate statistics for all tracked tokens.

#### Response
```json
{
  "total_tracked": 156,
  "rugged_count": 23,
  "safe_count": 45,
  "tracked_today": 12,
  "rug_rate": 14.7
}
```

---

### 6. Recent Tokens

**GET** `/api/v1/tokens/recent`

Get recently discovered tokens.

#### Query Parameters
- `limit` (optional): Number of tokens (default: 50, max: 100)

#### Response
```json
{
  "tokens": [
    {
      "address": "EQ...",
      "symbol": "DOGE",
      "name": "Dogecoin TON",
      "safety_score": 82,
      "holder_count": 234,
      "top_holder_pct": 12.3,
      "liquidity_usd": 45000.00,
      "first_seen": "2024-12-23T10:00:00Z",
      "rugged": false
    }
  ],
  "count": 50
}
```

---

### 7. Rugged Tokens

**GET** `/api/v1/tokens/rugged`

Get tokens that have been marked as rugged.

#### Query Parameters
- `limit` (optional): Number of tokens (default: 50)

#### Response
```json
{
  "tokens": [
    {
      "address": "EQ...",
      "symbol": "SCAM",
      "name": "ScamCoin",
      "safety_score": 15,
      "rugged": true,
      "rugged_at": "2024-12-22T15:30:00Z",
      "initial_holder_count": 50,
      "current_holder_count": 3
    }
  ],
  "count": 23
}
```

---

### 8. Live Token Feed (SSE)

**GET** `/api/v1/tokens/live`

Server-Sent Events stream for real-time token updates.

#### Response Format
```
data: {"type": "stats", "total_tracked": 156, "safe_count": 45, "rugged_count": 23, "rug_rate": 14.7}

data: {"type": "new_token", "address": "EQ...", "symbol": "PEPE", "safety_score": 75}

data: {"type": "rug_detected", "address": "EQ...", "symbol": "SCAM"}
```

#### JavaScript Example
```javascript
const evtSource = new EventSource('/api/v1/tokens/live');

evtSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'stats') {
    updateDashboard(data);
  } else if (data.type === 'new_token') {
    addTokenToFeed(data);
  } else if (data.type === 'rug_detected') {
    alertRugDetected(data);
  }
};
```

---

### 9. Live Feed Dashboard

**GET** `/feed`

Web page with real-time cyberpunk dashboard showing live token activity.

- Real-time stats updates via SSE
- Token discovery feed
- Rug detection alerts
- Responsive design

---

## Changelog

### v2.2 (2025-12-23)
- ✅ Token tracking API (`/api/v1/tokens/*`)
- ✅ Rug score endpoint (`/score/{address}`)
- ✅ Live SSE feed (`/api/v1/tokens/live`)
- ✅ Live dashboard (`/feed`)

### v2.1 (2025-12-04)
- ✅ TonAPI webhooks for instant payment detection
- ✅ X/Twitter auto-posting

### v2.0 (2025-11-24)
- ✅ Public API endpoints
- ✅ Batch notarization
- ✅ Public verification
- ✅ Referral system
- ✅ Telegram Stars payments

### v1.0 (2025-11-01)
- Initial release
- Telegram bot
- Manual notarization
- Group monitoring
