# MemeSeal E2E Tests

End-to-end testing suite using Puppeteer for browser automation.

## Quick Start

```bash
cd e2e
npm install
npm test
```

## Test Suites

### API Tests (`api.test.js`)
Tests all public API endpoints:
- `/api/v1/memescan/trending` - Trending tokens
- `/api/v1/memescan/new` - New token launches
- `/api/v1/memescan/pools` - DEX pools
- `/api/v1/memescan/check/:address` - Token safety check
- `/stats` - Bot statistics
- Health checks for all pages

### Page Tests (`pages.test.js`)
Browser-based tests for landing pages:
- MemeSeal landing page (CTAs, Telegram links)
- MemeScan landing page
- Verify page (input, button)
- Docs page
- Static assets (whitepaper PDF, favicon)

### App Tests (`app.test.js`)
Telegram Mini App tests:
- App loading and branding
- Tab navigation (TRENDING, NEW, CHECK, POOLS)
- Data loading from API
- Safety check feature
- Error handling
- Visual elements (CRT overlay, fonts)

## Running Tests

```bash
# All tests
npm test

# Verbose output
npm run test:verbose

# Individual suites
npm run test:api
npm run test:pages
npm run test:app
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE` | `https://notaryton.com` | Backend API URL |
| `APP_URL` | `https://memescan-ton.vercel.app` | Mini app URL |

Example:
```bash
API_BASE=http://localhost:8000 npm test
```

## Test Results

```
# tests 42
# pass 42
# fail 0
```

## Adding Tests

Tests use Node.js built-in test runner:

```javascript
const { describe, it } = require('node:test');
const assert = require('node:assert');

describe('My Feature', () => {
  it('should work', async () => {
    // API test
    const res = await fetch('https://notaryton.com/api/...');
    assert.strictEqual(res.status, 200);
  });
});
```

For browser tests with Puppeteer:

```javascript
const puppeteer = require('puppeteer');

describe('Browser Test', () => {
  let browser, page;

  before(async () => {
    browser = await puppeteer.launch({ headless: 'new' });
    page = await browser.newPage();
  });

  after(async () => {
    await browser.close();
  });

  it('loads page', async () => {
    await page.goto('https://example.com');
    // assertions...
  });
});
```

## CI/CD

Add to GitHub Actions:

```yaml
- name: Run E2E Tests
  run: |
    cd e2e
    npm install
    npm test
```
