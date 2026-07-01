
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

async function waitHub(page) {
  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule?as_of=2026-07-03', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await waitGone(page, 'Loading schedule intelligence');
  const anchors = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Baseline Anchors' }) }).first();
  await anchors.waitFor({ state: 'visible', timeout: 120000 });
  await waitGone(page, 'Loading baseline selections');
  for (const t of ['Current Contract Baseline', 'Previous Progress Update Baseline', 'Secondary Progress Update Baseline']) {
    await anchors.getByText(t, { exact: true }).waitFor({ timeout: 120000 });
  }
}

async function selectBasis(page, label) {
  const btn = page.getByRole('button', { name: label, exact: true });
  await btn.first().click();
  await page.waitForTimeout(2500);
  await waitGone(page, 'Loading schedule controls');
  await assertNotLoading(page, 'controls-' + label);
}

async function waitControlsNamed(page, pattern) {
  const controls = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Schedule Controls' }) }).first();
  await controls.waitFor({ state: 'visible', timeout: 120000 });
  await controls.getByText(pattern, { exact: false }).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'controls');
}

async function waitWorkbench(page, basisPattern) {
  await page.getByRole('heading', { name: 'Schedule Workbench' }).waitFor({ timeout: 120000 });
  await waitGone(page, 'Loading schedule workbench');
  await page.getByText(basisPattern, { exact: false }).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'workbench');
}

async function waitDriver(page, basisPattern) {
  await waitGone(page, 'Loading driver detail');
  await page.getByText('Side-by-Side Movement', { exact: true }).waitFor({ timeout: 120000 });
  await page.getByText(basisPattern, { exact: false }).first().waitFor({ timeout: 120000 });
  await assertNotLoading(page, 'driver');
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(() => localStorage.setItem('hb-ui-role', 'operator'));
  const shots = "/Users/bobbyfetting/hb-personal-assistant-worktrees/fix/schedule-named-baseline-production-readiness-phase13c-20260701T140807Z/docs/evidence/project-schedule-hub/named-baseline-production-readiness-phase13c-20260701T140807Z/12-browser-screenshots";
  const proof = { stamp: '2026-07-01T14:39:31Z', as_of: '2026-07-03', shots: [] };

  function record(file, surface, loaded, extra = {}) {
    proof.shots.push({ file, surface, loaded, ...extra });
  }

  await waitHub(page);
  await page.screenshot({ path: shots + '/01-schedule-hub-named-baselines.png', fullPage: true });
  record('01-schedule-hub-named-baselines.png', 'Schedule hub + Baseline Anchors', true);

  await selectBasis(page, 'Current Contract Baseline');
  await waitControlsNamed(page, /Comparing against Current Contract Baseline/i);
  await page.screenshot({ path: shots + '/02-controls-current-contract-baseline.png', fullPage: true });
  record('02-controls-current-contract-baseline.png', 'Controls current_contract_baseline', true);

  await waitHub(page);
  await selectBasis(page, 'Previous Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Previous Progress Update Baseline/i);
  await page.screenshot({ path: shots + '/03-controls-previous-progress-baseline.png', fullPage: true });
  record('03-controls-previous-progress-baseline.png', 'Controls previous_progress_update_baseline', true);

  await waitHub(page);
  await selectBasis(page, 'Secondary Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Secondary Progress Update Baseline/i);
  await page.screenshot({ path: shots + '/04-controls-secondary-progress-baseline.png', fullPage: true });
  record('04-controls-secondary-progress-baseline.png', 'Controls secondary_progress_update_baseline', true);

  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await waitWorkbench(page, /Comparing against Current Contract Baseline|current contract baseline/i);
  await page.screenshot({ path: shots + '/05-workbench-named-baseline-filter.png', fullPage: true });
  record('05-workbench-named-baseline-filter.png', 'Workbench named-baseline filter', true);

  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule/driver-detail?activity_id=FILTER-OUT-50&comparison_basis=current_contract_baseline&as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await waitDriver(page, /Comparing against Current Contract Baseline/i);
  await page.screenshot({ path: shots + '/06-driver-detail-named-baseline.png', fullPage: true });
  record('06-driver-detail-named-baseline.png', 'Driver detail named baseline context', true);

  await page.goto('http://127.0.0.1:5173/projects/tropical/schedule/driver-detail?activity_id=FILTER-OUT-50&comparison_basis=current_contract_baseline&as_of=2026-07-03', { waitUntil: 'domcontentloaded' });
  await waitDriver(page, /Comparing against Current Contract Baseline/i);
  await page.getByRole('heading', { name: 'Review Disposition' }).waitFor({ timeout: 120000 });
  const primary = await page.locator('section').filter({ has: page.getByRole('heading', { name: 'Review Disposition' }) }).first().textContent();
  if (/psri-|psnbri-/i.test(primary || '')) throw new Error('raw review item id visible in disposition card');
  await page.screenshot({ path: shots + '/07-driver-detail-disposition.png', fullPage: true });
  record('07-driver-detail-disposition.png', 'Driver detail Review Disposition card', true);

  await waitHub(page);
  const controlsCard = page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'Schedule Controls' }) }).first();
  await selectBasis(page, 'Prior Update');
  await waitControlsNamed(page, /Comparing against Prior Update/i);
  const priorText = await controlsCard.getByText(/finish.*later|moved later/i).first().textContent().catch(() => '');
  await selectBasis(page, 'Secondary Progress Update Baseline');
  await waitControlsNamed(page, /Comparing against Secondary Progress Update Baseline/i);
  const namedText = await controlsCard.getByText(/finish.*later|moved later/i).first().textContent().catch(() => '');
  if (!priorText || !namedText) throw new Error('scope isolation movement text missing');
  await page.screenshot({ path: shots + '/08-scope-isolation-prior-vs-named.png', fullPage: true });
  record('08-scope-isolation-prior-vs-named.png', 'prior_update vs named-baseline scope isolation', true,
    { prior_movement_snippet: priorText.slice(0, 120), named_movement_snippet: namedText.slice(0, 120) });

  proof.fully_loaded_required = proof.shots.every(s => s.loaded);
  console.log(JSON.stringify(proof, null, 2));
  await browser.close();
})();
