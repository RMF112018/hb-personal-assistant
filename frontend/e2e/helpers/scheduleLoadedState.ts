/** Loaded-state recipe definitions for schedule-tool evidence screenshots. */

export type LoadedStateProof = {
  page: string
  url: string
  api_response_matched: boolean
  loaded_heading_found: boolean
  loading_state_absent: boolean
  expected_content_found: boolean
  screenshot_path: string
}

export type ScheduleLoadedStateRecipe = {
  page: string
  apiUrlPattern: string | RegExp
  headingText: string
  loadingMarkers: string[]
  expectedContent: string
  timeoutMs?: number
}

export const SCHEDULE_LOADING_MARKERS = [
  'Loading schedule intelligence',
  'Loading schedule controls',
  'Loading schedule workbench',
  'Loading driver detail',
  'Loading baseline selections',
  'Loading schedule review dashboard',
  'Project workspace could not be loaded',
]

export const SCHEDULE_LOADED_STATE_RECIPES: Record<string, ScheduleLoadedStateRecipe> = {
  schedule_hub: {
    page: 'schedule_hub',
    apiUrlPattern: /\/api\/projects\/[^/]+\/schedule\b/,
    headingText: 'Schedule Intelligence',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'Baseline Anchors',
  },
  schedule_import: {
    page: 'schedule_import',
    apiUrlPattern: /\/api\/schedules\/import-preview|\/schedule\/import/,
    headingText: 'Schedule Import',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'Import Preview',
  },
  schedule_controls: {
    page: 'schedule_controls',
    apiUrlPattern: /\/api\/projects\/[^/]+\/schedule\/controls/,
    headingText: 'Schedule Controls',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'Comparing against',
  },
  schedule_workbench: {
    page: 'schedule_workbench',
    apiUrlPattern: /\/api\/projects\/[^/]+\/schedule\/review-items/,
    headingText: 'Schedule Workbench',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'current contract baseline',
  },
  schedule_review_dashboard: {
    page: 'schedule_review_dashboard',
    apiUrlPattern: /\/api\/projects\/schedule-review-dashboard/,
    headingText: 'Schedule Review Dashboard',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'Total projects',
  },
  driver_detail: {
    page: 'driver_detail',
    apiUrlPattern: /\/api\/projects\/[^/]+\/schedule\/drivers/,
    headingText: 'Driver Detail',
    loadingMarkers: SCHEDULE_LOADING_MARKERS,
    expectedContent: 'Side-by-Side Movement',
  },
}

export function buildLoadedStateProof(input: {
  recipe: ScheduleLoadedStateRecipe
  url: string
  screenshotPath: string
  checks: Partial<LoadedStateProof>
}): LoadedStateProof {
  return {
    page: input.recipe.page,
    url: input.url,
    api_response_matched: Boolean(input.checks.api_response_matched),
    loaded_heading_found: Boolean(input.checks.loaded_heading_found),
    loading_state_absent: Boolean(input.checks.loading_state_absent),
    expected_content_found: Boolean(input.checks.expected_content_found),
    screenshot_path: input.screenshotPath,
  }
}

export function validateLoadedStateProof(proof: LoadedStateProof): boolean {
  return (
    proof.api_response_matched &&
    proof.loaded_heading_found &&
    proof.loading_state_absent &&
    proof.expected_content_found &&
    proof.screenshot_path.length > 0
  )
}

export function recipeForPage(page: string): ScheduleLoadedStateRecipe | undefined {
  return SCHEDULE_LOADED_STATE_RECIPES[page]
}
