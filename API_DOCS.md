# NotaryTON API Documentation

## Base URL
```
Production: https://notaryton.com
```

## Authentication
Use your Telegram user ID as the API key. Get it via `/api` command in @NotaryTON_bot.

**Requirements**: Active subscription (0.1 TON/month)

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
| 401 | No active subscription | Subscribe via @NotaryTON_bot |
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

- **Telegram**: @NotaryTON_bot
- **Issues**: [GitHub Issues](https://github.com/cherishwins/notaryton-bot/issues)
- **Docs**: https://notaryton.com/docs

---

## Changelog

### v2.0 (2025-11-24)
- ✅ Public API endpoints
- ✅ Batch notarization
- ✅ Public verification
- ✅ Referral system
- ✅ Automated payment polling

### v1.0 (2025-11-01)
- Initial release
- Telegram bot
- Manual notarization
- Group monitoring
