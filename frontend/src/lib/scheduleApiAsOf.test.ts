import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getProjectScheduleBaseline,
  getProjectScheduleControls,
  getProjectScheduleDrilldown,
  getProjectScheduleMetricTrends,
  getProjectScheduleReviewItems,
  getProjectScheduleSummary,
  syncProjectScheduleReviewItems,
} from './api';

function jsonResponse(body: unknown = {}) {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => body,
  } as Response;
}

describe('schedule API as-of helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('emits as_of for summary and baseline only when asOf is non-empty', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal('fetch', fetchMock);

    await getProjectScheduleSummary('tropical', { asOf: '2026-06-16' });
    await getProjectScheduleBaseline('tropical', { asOf: '2026-06-16' });
    await getProjectScheduleSummary('tropical', { asOf: '' });
    await getProjectScheduleBaseline('tropical', { asOf: null });

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/projects/tropical/schedule?as_of=2026-06-16',
      '/api/projects/tropical/schedule/baseline?as_of=2026-06-16',
      '/api/projects/tropical/schedule',
      '/api/projects/tropical/schedule/baseline',
    ]);
  });

  it('uses the same asOf option name for trend, drilldown, and review requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal('fetch', fetchMock);

    await getProjectScheduleMetricTrends('tropical', { asOf: '2026-06-16', metrics: ['delay_analysis'] });
    await getProjectScheduleDrilldown('tropical', 'upstream_cues', { asOf: '2026-06-16', limit: 10 });
    await getProjectScheduleReviewItems('tropical', { asOf: '2026-06-16', reviewStatus: 'open' });

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/projects/tropical/schedule/metrics/trends?as_of=2026-06-16&metrics=delay_analysis',
      '/api/projects/tropical/schedule/drilldowns?type=upstream_cues&limit=10&as_of=2026-06-16',
      '/api/projects/tropical/schedule/review-items?review_status=open&as_of=2026-06-16',
    ]);
  });

  it('emits comparison_basis for review sync POST requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal('fetch', fetchMock);

    await syncProjectScheduleReviewItems('tropical', {
      asOf: '2026-06-16',
      comparisonBasis: 'baseline',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/projects/tropical/schedule/review-items?as_of=2026-06-16&comparison_basis=baseline',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('emits as_of and comparison_basis for controls requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse());
    vi.stubGlobal('fetch', fetchMock);

    await getProjectScheduleControls('tropical', {
      asOf: '2026-06-16',
      comparisonBasis: 'baseline',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/projects/tropical/schedule/controls?as_of=2026-06-16&comparison_basis=baseline',
      expect.objectContaining({}),
    );
  });
});
