const { chromium } = require('playwright');
const path = require('path');

const EVIDENCE = __dirname;
const LOADING = ['Loading schedule review dashboard', 'Refreshing portfolio'];

async function waitGone(page, text, ms = 120000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if ((await page.getByText(text, { exact: false }).count()) === 0) return;
    await page.waitForTimeout(300);
  }
  throw new Error('timeout waiting for: ' + text);
}

async function waitLoaded(page) {
  for (const marker of LOADING) await waitGone(page, marker);
  await page.getByRole('heading', { name: 'Schedule Review Dashboard' }).waitFor({ timeout: 120000 });
  await page.getByText('Total projects', { exact: true }).waitFor({ timeout: 120000 });
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'viewer'));

  const shots = [
    ['09-browser-dashboard-overview.png', ''],
    ['10-browser-dashboard-filter-blocked.png', 'Blocked'],
    ['11-browser-dashboard-filter-stale.png', 'Stale schedule'],
    ['12-browser-dashboard-filter-needs-review.png', 'Needs review'],
    ['13-browser-dashboard-empty-state.png', 'Ready'],
    ['14-browser-navigation-entry.png', 'NAV'],
  ];

  await page.goto('http://127.0.0.1:5173/projects/all/schedule/review', { waitUntil: 'domcontentloaded' });
  await waitLoaded(page);
  await page.screenshot({ path: path.join(EVIDENCE, shots[0][0]), fullPage: true });

  for (const [file, label] of shots.slice(1, 5)) {
    if (label === 'Ready') {
      await page.getByRole('button', { name: label, exact: true }).click();
      await page.waitForTimeout(800);
      await waitGone(page, 'Refreshing portfolio');
      const empty = page.getByText('All visible projects are clear', { exact: false });
      const table = page.getByTestId('portfolio-project-table');
      const summary = page.getByText('Total projects', { exact: true });
      await Promise.race([
        empty.waitFor({ timeout: 120000 }),
        table.waitFor({ timeout: 120000 }),
        summary.waitFor({ timeout: 120000 }),
      ]);
    } else {
      await page.getByRole('button', { name: label, exact: true }).click();
      await page.waitForTimeout(800);
      await waitGone(page, 'Refreshing portfolio');
      await waitLoaded(page);
    }
    await page.screenshot({ path: path.join(EVIDENCE, file), fullPage: true });
  }

  await page.goto('http://127.0.0.1:5173/projects/all', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Schedule Review Dashboard' }).waitFor({ timeout: 120000 });
  await page.screenshot({ path: path.join(EVIDENCE, shots[5][0]), fullPage: true });

  await browser.close();
  console.log(JSON.stringify({ ok: true, shots: shots.map(([f]) => f) }, null, 2));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
