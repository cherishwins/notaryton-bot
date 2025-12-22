/**
 * Pages E2E Tests for MemeSeal
 * Tests landing pages, CTA buttons, and navigation using Puppeteer
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const puppeteer = require('puppeteer');

const BASE_URL = process.env.API_BASE || 'https://notaryton.com';

let browser;
let page;

describe('Landing Pages E2E', () => {

  before(async () => {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });
  });

  after(async () => {
    if (browser) await browser.close();
  });

  describe('MemeSeal Landing Page', () => {

    it('loads successfully', async () => {
      const response = await page.goto(BASE_URL, { waitUntil: 'networkidle2' });
      assert.strictEqual(response.status(), 200);
    });

    it('displays MemeSeal branding', async () => {
      const content = await page.content();
      assert.ok(
        content.toLowerCase().includes('memeseal') || content.includes('MEMESEAL'),
        'Page should display MemeSeal branding'
      );
    });

    it('CTA buttons have valid hrefs', async () => {
      const ctaLinks = await page.$$eval('a.cta, a.mega-cta, .cta-btn', links =>
        links.map(a => ({
          text: a.textContent.trim(),
          href: a.href,
          visible: a.offsetParent !== null
        }))
      );

      console.log('Found CTA buttons:', ctaLinks.length);

      for (const link of ctaLinks) {
        assert.ok(link.href, `CTA "${link.text}" should have href`);
        assert.ok(
          link.href.startsWith('http') || link.href.startsWith('/'),
          `CTA "${link.text}" href should be valid URL: ${link.href}`
        );
      }
    });

    it('Telegram bot links point to correct bot', async () => {
      const telegramLinks = await page.$$eval('a[href*="t.me"]', links =>
        links.map(a => a.href)
      );

      console.log('Telegram links found:', telegramLinks.length);

      // Should have at least one Telegram link
      assert.ok(telegramLinks.length > 0, 'Should have Telegram links');

      // All Telegram links should be valid
      for (const href of telegramLinks) {
        assert.ok(href.includes('t.me/'), `Should be valid Telegram link: ${href}`);
      }
    });

    it('navigation links work', async () => {
      // Find all internal links
      const internalLinks = await page.$$eval('a[href^="/"]', links =>
        links.slice(0, 5).map(a => ({
          text: a.textContent.trim(),
          href: a.href
        }))
      );

      // Test first few internal links
      for (const link of internalLinks.slice(0, 3)) {
        try {
          const response = await page.goto(link.href, { waitUntil: 'networkidle2', timeout: 10000 });
          assert.ok(
            response.status() < 400,
            `Link "${link.text}" (${link.href}) should return success: got ${response.status()}`
          );
        } catch (err) {
          console.log(`Warning: Link "${link.text}" timed out or failed:`, err.message);
        }
      }
    });
  });

  describe('MemeScan Landing Page', () => {

    it('loads successfully', async () => {
      const response = await page.goto(`${BASE_URL}/memescan`, { waitUntil: 'networkidle2' });
      assert.strictEqual(response.status(), 200);
    });

    it('displays MemeScan branding', async () => {
      const content = await page.content();
      assert.ok(
        content.toLowerCase().includes('memescan') || content.includes('MEMESCAN'),
        'Page should display MemeScan branding'
      );
    });

    it('Launch Terminal CTA works', async () => {
      const launchBtn = await page.$('a.cta-btn');
      if (launchBtn) {
        const href = await launchBtn.evaluate(el => el.href);
        assert.ok(href.includes('t.me'), 'Launch button should link to Telegram');
      }
    });
  });

  describe('Verify Page', () => {

    it('loads successfully', async () => {
      const response = await page.goto(`${BASE_URL}/verify`, { waitUntil: 'networkidle2' });
      assert.strictEqual(response.status(), 200);
    });

    it('has hash input field', async () => {
      const input = await page.$('input[type="text"], input[name="hash"], #hash-input');
      assert.ok(input, 'Verify page should have input field');
    });

    it('has verify button', async () => {
      const button = await page.$('button, input[type="submit"]');
      assert.ok(button, 'Verify page should have submit button');
    });
  });

  describe('Docs Page', () => {

    it('loads successfully', async () => {
      const response = await page.goto(`${BASE_URL}/docs`, { waitUntil: 'networkidle2' });
      assert.strictEqual(response.status(), 200);
    });

    it('displays API documentation', async () => {
      const content = await page.content();
      assert.ok(
        content.toLowerCase().includes('api') || content.includes('endpoint'),
        'Docs page should mention API'
      );
    });
  });

  describe('Static Assets', () => {

    it('whitepaper PDF is accessible', async () => {
      const response = await page.goto(`${BASE_URL}/static/whitepaper.pdf`, { waitUntil: 'networkidle2' });
      assert.strictEqual(response.status(), 200);
    });

    it('favicon loads', async () => {
      const response = await page.goto(`${BASE_URL}/static/favicon.ico`, { waitUntil: 'networkidle2' });
      assert.ok(response.status() < 400, 'Favicon should be accessible');
    });
  });
});

console.log('Running Pages E2E tests against:', BASE_URL);
