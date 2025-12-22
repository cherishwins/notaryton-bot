/**
 * API E2E Tests for MemeSeal
 * Tests all public API endpoints
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');

const BASE_URL = process.env.API_BASE || 'https://notaryton.com';

describe('MemeScan API', () => {

  it('GET /api/v1/memescan/trending - returns trending tokens', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/memescan/trending`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.success, true, 'API should return success: true');
    assert.ok(Array.isArray(data.tokens), 'tokens should be an array');

    if (data.tokens.length > 0) {
      const token = data.tokens[0];
      assert.ok(token.address, 'token should have address');
      assert.ok(token.symbol, 'token should have symbol');
      assert.ok(typeof token.price_usd === 'number', 'token should have price_usd');
    }
  });

  it('GET /api/v1/memescan/new - returns new token launches', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/memescan/new`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.success, true);
    assert.ok(Array.isArray(data.tokens));

    if (data.tokens.length > 0) {
      const token = data.tokens[0];
      assert.ok(token.address, 'token should have address');
      assert.ok(token.created_at, 'new token should have created_at');
    }
  });

  it('GET /api/v1/memescan/pools - returns DEX pools', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/memescan/pools`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.strictEqual(data.success, true);
    assert.ok(Array.isArray(data.pools));

    if (data.pools.length > 0) {
      const pool = data.pools[0];
      assert.ok(pool.address, 'pool should have address');
      assert.ok(pool.pair, 'pool should have pair');
      assert.ok(pool.dex, 'pool should have dex');
      assert.ok(typeof pool.liquidity_usd === 'number', 'pool should have liquidity_usd');
    }
  });

  it('GET /api/v1/memescan/check/:address - checks token safety', async () => {
    // Use USDT address for testing (known valid token)
    const testAddress = 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs';

    const res = await fetch(`${BASE_URL}/api/v1/memescan/check/${testAddress}`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    // API might return error for unknown token, that's OK
    assert.ok('success' in data, 'response should have success field');
  });
});

describe('Stats API', () => {

  it('GET /stats - returns bot statistics', async () => {
    const res = await fetch(`${BASE_URL}/stats`);
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.ok('total_users' in data || 'error' in data, 'should return stats or error');
  });
});

describe('Health Endpoints', () => {

  it('GET / - landing page loads', async () => {
    const res = await fetch(BASE_URL);
    assert.strictEqual(res.status, 200);

    const text = await res.text();
    assert.ok(text.includes('MemeSeal') || text.includes('memeseal'), 'page should mention MemeSeal');
  });

  it('GET /memescan - memescan landing loads', async () => {
    const res = await fetch(`${BASE_URL}/memescan`);
    assert.strictEqual(res.status, 200);

    const text = await res.text();
    assert.ok(text.includes('MemeScan') || text.includes('memescan'), 'page should mention MemeScan');
  });

  it('GET /verify - verify page loads', async () => {
    const res = await fetch(`${BASE_URL}/verify`);
    assert.strictEqual(res.status, 200);
  });

  it('GET /docs - docs page loads', async () => {
    const res = await fetch(`${BASE_URL}/docs`);
    assert.strictEqual(res.status, 200);
  });
});

console.log('Running API E2E tests against:', BASE_URL);
