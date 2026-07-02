import { describe, expect, it } from 'vitest'

import {
  SCHEDULE_LOADED_STATE_RECIPES,
  SCHEDULE_LOADING_MARKERS,
  buildLoadedStateProof,
  recipeForPage,
  validateLoadedStateProof,
} from './scheduleLoadedState'

describe('scheduleLoadedState recipes', () => {
  it('defines all required page recipes', () => {
    for (const page of [
      'schedule_hub',
      'schedule_import',
      'schedule_controls',
      'schedule_workbench',
      'schedule_review_dashboard',
      'driver_detail',
    ]) {
      expect(recipeForPage(page)?.page).toBe(page)
    }
  })

  it('builds proof JSON with required fields', () => {
    const recipe = SCHEDULE_LOADED_STATE_RECIPES.schedule_hub
    const proof = buildLoadedStateProof({
      recipe,
      url: 'http://127.0.0.1:5173/projects/tropical/schedule',
      screenshotPath: '/tmp/hub.png',
      checks: {
        api_response_matched: true,
        loaded_heading_found: true,
        loading_state_absent: true,
        expected_content_found: true,
      },
    })
    expect(validateLoadedStateProof(proof)).toBe(true)
    expect(proof.page).toBe('schedule_hub')
  })

  it('tracks common loading markers', () => {
    expect(SCHEDULE_LOADING_MARKERS.length).toBeGreaterThan(3)
    expect(SCHEDULE_LOADING_MARKERS.join(' ')).toContain('Loading schedule intelligence')
  })
})
