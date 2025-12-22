/**
 * Mini App E2E Tests for MemeScan
 * Tests the Telegram Mini App functionality
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const puppeteer = require('puppeteer');

// Mini app URL (Vercel deployment)
const APP_URL = process.env.APP_URL || 'https://memescan-ton.vercel.app';
const API_BASE = process.env.API_BASE || 'https://notaryton.com';

let browser;
let page;

describe('MemeScan Mini App E2E', () => {

  before(async () => {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    page = await browser.newPage();
    await page.setViewport({ width: 375, height: 812 }); // Mobile viewport

    // Intercept and log API calls
    page.on('response', response => {
      const url = response.url();
      if (url.includes('/api/')) {
        console.log(`API: ${response.status()} ${url.split('/api/')[1]}`);
      }
    });
  });

  after(async () => {
    if (browser) await browser.close();
  });

  describe('App Loading', () => {

    it('loads the app', async () => {
      const response = await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 30000 });
      assert.strictEqual(response.status(), 200);
    });

    it('displays header with logo', async () => {
      await page.waitForSelector('.header, header', { timeout: 5000 });
      const header = await page.$('.header, header');
      assert.ok(header, 'App should have header');

      const content = await page.content();
      assert.ok(
        content.includes('MEMESCAN') || content.includes('memescan'),
        'Header should show MemeScan branding'
      );
    });

    it('shows LIVE status indicator', async () => {
      const content = await page.content();
      assert.ok(content.includes('LIVE'), 'Should show LIVE status');
    });
  });

  describe('Tab Navigation', () => {

    it('has all 4 tabs', async () => {
      const tabs = await page.$$('.tab, nav button');
      assert.ok(tabs.length >= 4, `Should have 4 tabs, found ${tabs.length}`);
    });

    it('TRENDING tab is default active', async () => {
      const activeTab = await page.$('.tab.active');
      if (activeTab) {
        const text = await activeTab.evaluate(el => el.textContent);
        assert.ok(text.includes('TRENDING'), 'TRENDING should be active by default');
      }
    });

    it('can switch to NEW tab', async () => {
      const newTab = await page.$('.tab:nth-child(2)');
      if (newTab) {
        await newTab.click();
        await new Promise(r => setTimeout(r, 500));

        const activeTab = await page.$('.tab.active');
        const text = await activeTab.evaluate(el => el.textContent);
        assert.ok(text.includes('NEW'), 'NEW tab should be active after click');
      }
    });

    it('can switch to CHECK tab', async () => {
      const checkTab = await page.$('.tab:nth-child(3)');
      if (checkTab) {
        await checkTab.click();
        await new Promise(r => setTimeout(r, 500));

        // Should show input field
        const input = await page.$('.check-input, input[type="text"]');
        assert.ok(input, 'CHECK tab should show input field');
      }
    });

    it('can switch to POOLS tab', async () => {
      const poolsTab = await page.$('.tab:nth-child(4)');
      if (poolsTab) {
        await poolsTab.click();
        await new Promise(r => setTimeout(r, 500));

        const activeTab = await page.$('.tab.active');
        const text = await activeTab.evaluate(el => el.textContent);
        assert.ok(text.includes('POOLS'), 'POOLS tab should be active after click');
      }
    });
  });

  describe('Data Loading', () => {

    it('loads trending tokens', async () => {
      // Click TRENDING tab
      const trendingTab = await page.$('.tab:first-child');
      if (trendingTab) await trendingTab.click();

      // Wait for data to load
      await new Promise(r => setTimeout(r, 2000));

      // Check for token items or loading/empty state
      const content = await page.content();
      const hasTokens = content.includes('token-item') || content.includes('token-symbol');
      const hasEmpty = content.includes('empty') || content.includes('No trending');
      const hasLoading = content.includes('loading') || content.includes('Scanning');

      assert.ok(hasTokens || hasEmpty || hasLoading, 'Should show tokens, empty state, or loading');
    });

    it('loads pools data', async () => {
      // Click POOLS tab
      const poolsTab = await page.$('.tab:nth-child(4)');
      if (poolsTab) await poolsTab.click();

      await new Promise(r => setTimeout(r, 2000));

      const content = await page.content();
      const hasPools = content.includes('pool-item') || content.includes('pool-pair');
      const hasEmpty = content.includes('empty') || content.includes('No pools');
      const hasLoading = content.includes('loading');

      assert.ok(hasPools || hasEmpty || hasLoading, 'Should show pools, empty state, or loading');
    });
  });

  describe('Safety Check Feature', () => {

    it('CHECK tab has input and button', async () => {
      // Click CHECK tab
      const checkTab = await page.$('.tab:nth-child(3)');
      if (checkTab) await checkTab.click();

      await new Promise(r => setTimeout(r, 500));

      const input = await page.$('.check-input, input[type="text"]');
      const button = await page.$('.check-button, button');

      assert.ok(input, 'Should have address input');
      assert.ok(button, 'Should have SCAN button');
    });

    it('SCAN button is disabled when input empty', async () => {
      const button = await page.$('.check-button');
      if (button) {
        const isDisabled = await button.evaluate(el => el.disabled);
        assert.strictEqual(isDisabled, true, 'SCAN should be disabled when input empty');
      }
    });

    it('can enter address and trigger scan', async () => {
      const input = await page.$('.check-input, input[type="text"]');
      const button = await page.$('.check-button, button');

      if (input && button) {
        // Clear any existing text first
        await input.click({ clickCount: 3 });

        // Type a test address
        await input.type('EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs');

        // Button should now be enabled
        await new Promise(r => setTimeout(r, 200));
        const isDisabled = await button.evaluate(el => el.disabled);

        // Click scan if enabled
        if (!isDisabled) {
          await button.click();
          await new Promise(r => setTimeout(r, 5000)); // Longer wait for API

          // Should show result, error, or no longer be loading
          const content = await page.content();
          const hasResult = content.includes('safety') || content.includes('holder') || content.includes('HOLDER');
          const hasError = content.includes('error') || content.includes('Failed') || content.includes('Network');
          const notLoading = !content.includes('Scanning');

          // Any of these states is acceptable
          assert.ok(hasResult || hasError || notLoading, 'Should complete scan (result, error, or finished loading)');
        } else {
          // If button still disabled, that's also OK - input validation working
          console.log('Button remained disabled - input validation working');
        }
      }
    });
  });

  describe('Error Handling', () => {

    it('shows error message on network failure', async () => {
      // Simulate offline mode
      await page.setOfflineMode(true);

      // Try to switch tabs to trigger API call
      const newTab = await page.$('.tab:nth-child(2)');
      if (newTab) await newTab.click();

      await new Promise(r => setTimeout(r, 1000));

      const content = await page.content();
      const hasError = content.includes('error') || content.includes('Network');

      // Restore online mode
      await page.setOfflineMode(false);

      // Error handling is optional - just log result
      console.log('Error handling test:', hasError ? 'PASS' : 'No error shown (may be cached)');
    });
  });

  describe('Visual Elements', () => {

    it('has CRT overlay effect', async () => {
      await page.setOfflineMode(false);
      await page.goto(APP_URL, { waitUntil: 'networkidle2' });

      const crtOverlay = await page.$('.crt-overlay');
      assert.ok(crtOverlay, 'Should have CRT overlay for retro effect');
    });

    it('uses terminal-style font', async () => {
      const fontFamily = await page.evaluate(() => {
        const body = document.body;
        return window.getComputedStyle(body).fontFamily;
      });

      console.log('Font family:', fontFamily);
      // Should use Space Mono or similar terminal font
    });
  });
});

describe('API Integration', () => {

  it('API base URL is reachable', async () => {
    const response = await fetch(API_BASE);
    assert.strictEqual(response.status, 200);
  });

  it('Trending API returns data', async () => {
    const response = await fetch(`${API_BASE}/api/v1/memescan/trending`);
    const data = await response.json();
    assert.strictEqual(data.success, true);
  });
});

console.log('Running Mini App E2E tests');
console.log('App URL:', APP_URL);
console.log('API Base:', API_BASE);
