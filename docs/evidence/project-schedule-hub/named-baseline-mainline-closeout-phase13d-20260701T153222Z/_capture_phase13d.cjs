
const { chromium } = require('playwright');
const LOADING = ['Loading schedule intelligence', 'Loading schedule controls', 'Loading schedule workbench',
  'Loading driver detail', 'Loading baseline selections', 'Project workspace could not be loaded'];

async function waitGone(page, text, ms = 180000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if ((await page.getByText(text, { exact: false }).count()) === 0) return;
    await page.waitForTimeout(400);
  }
  throw new Error('timeout waiting for: ' + text);
}

async function assertNotLoading(page, label) {
  for (const m of LOADING) {
    if ((await page.getByText(m, { exact: false }).count()) > 0)
      throw new Error(label + ': still loading ' + m);
  }
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(120000);
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = "/Users/bobbyfetting/hb-personal-assistant-worktrees/verify/schedule-named-baseline-phase13d-mainline-20260701T153222Z/docs/evidence/project-schedule-hub/named-baseline-mainline-closeout-phase13d-20260701T153222Z/09-browser-smoke";
  const proof = { stamp: '2026-07-01T15:44:28Z', as_of: '2026-07-03', shots: [] };
  const record = (file, surface, loaded, extra = {}) => proof.shots.push({ file, surface, loaded, ...extra });

  // 01 hub
  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule?as_of=2026-07-03', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await waitGone(page, 'Loading schedule intelligence');
  const anchors = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Baseline Anchors' }) }).first();
  await anchors.waitFor({ state: 'visible', timeout: 120000 });
  await waitGone(page, 'Loading baseline selections');
  await waitGone(page, 'Loading schedule controls');
  await assertNotLoading(page, 'hub');
  await page.screenshot({ path: shots + '/01-schedule-hub-named-baselines.png', fullPage: true });
  record('01-schedule-hub-named-baselines.png', 'Schedule hub named baseline selector', true);

  // 02 controls contract
  const contractBtn = page.getByRole('button', { name: 'Current Contract Baseline', exact: true }).first();
  await contractBtn.click();
  await page.waitForTimeout(2500);
  await waitGone(page, 'Loading schedule controls');
  const controls = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Schedule Controls' }) }).first();
  await controls.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({ timeout: 120000 });
  await controls.getByText(/moved later/i).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'controls');
  await page.screenshot({ path: shots + '/02-controls-current-contract-baseline.png', fullPage: true });
  record('02-controls-current-contract-baseline.png', 'Controls current_contract_baseline movement', true);

  // 03 workbench
  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Schedule Workbench' }).waitFor({ timeout: 120000 });
  await waitGone(page, 'Loading schedule workbench');
  await page.getByText(/current contract baseline/i).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'workbench');
  await page.screenshot({ path: shots + '/03-workbench-named-baseline.png', fullPage: true });
  record('03-workbench-named-baseline.png', 'Workbench named comparison basis', true);

  // 04 driver detail + disposition
  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule/driver-detail?activity_id=FILTER-OUT-50&comparison_basis=current_contract_baseline&as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await waitGone(page, 'Loading driver detail');
  await page.getByText('Side-by-Side Movement', { exact: true }).waitFor({ timeout: 120000 });
  await page.getByRole('heading', { name: 'Review Disposition' }).waitFor({ timeout: 120000 });
  const disp = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Review Disposition' }) }).first();
  const dispText = await disp.textContent();
  if (/psri-|psnbri-/i.test(dispText || '')) throw new Error('raw review id in disposition card');
  await assertNotLoading(page, 'driver');
  await page.screenshot({ path: shots + '/04-driver-detail-disposition.png', fullPage: true });
  record('04-driver-detail-disposition.png', 'Driver detail named context + disposition', true);

  // 05 export control on hub with named basis
  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule?as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await waitGone(page, 'Loading schedule intelligence');
  const anchors2 = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Baseline Anchors' }) }).first();
  await anchors2.waitFor({ state: 'visible', timeout: 120000 });
  await waitGone(page, 'Loading schedule controls');
  await page.getByRole('button', { name: 'Current Contract Baseline', exact: true }).first().click();
  await waitGone(page, 'Loading schedule controls');
  const controls2 = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Schedule Controls' }) }).first();
  await controls2.getByText(/Comparing against Current Contract Baseline/i).first().waitFor({ timeout: 120000 });
  await page.getByRole('button', { name: 'Export Memo', exact: true }).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'export-ui');
  await page.screenshot({ path: shots + '/05-export-named-basis-selected.png', fullPage: true });
  record('05-export-named-basis-selected.png', 'Export control with named basis selected', true);

  proof.fully_loaded_required = proof.shots.every(s => s.loaded);
  console.log(JSON.stringify(proof, null, 2));
  await browser.close();
})();
