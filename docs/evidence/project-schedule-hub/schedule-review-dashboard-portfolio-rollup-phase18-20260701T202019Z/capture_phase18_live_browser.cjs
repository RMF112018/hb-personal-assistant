const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const expectedCount = Number(process.env.PHASE18_EXPECTED_PROJECT_COUNT || '0');
const screenshotPath = process.env.PHASE18_SCREENSHOT_PATH;
const dashboardUrl = process.env.PHASE18_DASHBOARD_URL || 'http://127.0.0.1:5174/projects/all/schedule/review';

if (!expectedCount || !screenshotPath) {
  console.error('PHASE18_EXPECTED_PROJECT_COUNT and PHASE18_SCREENSHOT_PATH are required');
  process.exit(1);
}

async function waitGone(page, text, ms = 300000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if ((await page.getByText(text, { exact: false }).count()) === 0) return;
    await page.waitForTimeout(400);
  }
  throw new Error('timeout waiting for: ' + text);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'viewer'));

  await page.goto(dashboardUrl, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await waitGone(page, 'Loading schedule review dashboard');
  await page.getByRole('heading', { name: 'Schedule Review Dashboard' }).waitFor({ timeout: 300000 });
  await page.getByText('Total projects', { exact: true }).waitFor({ timeout: 300000 });

  const totalCard = page.locator('.card').filter({ hasText: 'Total projects' }).first();
  await totalCard.waitFor({ state: 'visible', timeout: 120000 });
  const cardText = (await totalCard.textContent()) || '';
  const match = cardText.match(/(\d+)/);
  const domCount = match ? Number(match[1]) : NaN;
  if (domCount !== expectedCount) {
    throw new Error(
      `DOM/API mismatch: expected Total projects ${expectedCount} from live API, saw ${domCount} in card text: ${cardText}`,
    );
  }

  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  const proof = {
    ok: true,
    expected_project_count: expectedCount,
    dom_project_count: domCount,
    screenshot: path.basename(screenshotPath),
    dashboard_url: dashboardUrl,
  };
  console.log(JSON.stringify(proof, null, 2));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
