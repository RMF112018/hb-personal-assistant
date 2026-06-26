import http from 'node:http'
import fs from 'node:fs'

const source =
  'docs/evidence/schedule-import-health-foundation/20260626T090621Z/manual-zip-package-proof/TWN.zip/03-health-data.json'
const health = JSON.parse(fs.readFileSync(source, 'utf8')).payload
const version = health.schedule_version_key

const quality = {
  schedule_version_key: version,
  project_key: health.project_key,
  status: health.quality_summary.status,
  source_format: health.current_schedule.source_format,
  quality_score: health.quality_summary.scorecard.quality_score,
  quality_grade: health.quality_summary.scorecard.quality_grade,
  scorecard: health.quality_summary.scorecard,
  metrics: [
    {
      metric_family: 'dcma',
      metric_code: 'dcma_relationship_types',
      metric_name: 'Relationship types',
      numerator: 2235,
      denominator: 3718,
      value: 0.6011,
      unit: 'ratio',
      status: 'passed_threshold',
      evidence_json: JSON.stringify({ distribution: { FS: 2235, FF: 1357, SS: 125, SF: 1 } }),
    },
    {
      metric_family: 'source_export',
      metric_code: 'source_critical_path_available',
      metric_name: 'Source critical path available',
      numerator: 711,
      status: 'available_xer_total_float_threshold',
      evidence_json: JSON.stringify({
        source_critical_basis: 'xer_total_float_threshold',
        source_critical_path_type: 'CT_TotFloat',
        source_critical_activity_count: 711,
        source_driving_path_count: 327,
        explicit_float_activity_count: 712,
        driving_path_with_explicit_float_count: 27,
        activity_count: 1507,
        source_critical_float_threshold_hours: 0,
      }),
    },
  ],
  gao_category_summary: {
    critical_path_validity: {
      posture: 'partial',
      reason: 'source-export critical path evidence is present but CPM recalculation is required',
    },
  },
  top_findings: [],
}

function send(res, body, status = 200) {
  res.writeHead(status, {
    'content-type': 'application/json',
    'access-control-allow-origin': '*',
  })
  res.end(JSON.stringify(body))
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', 'http://127.0.0.1:8000')
  const projectVersionsPath = `/api/schedules/projects/${encodeURIComponent(health.project_key)}/versions`
  const rawProjectVersionsPath = `/api/schedules/projects/${health.project_key}/versions`

  if (url.pathname === '/api/schedules/projects') {
    send(res, { projects: [{ project_key: health.project_key, display_name: 'TWN Manual Proof' }] })
    return
  }
  if (url.pathname === projectVersionsPath || url.pathname === rawProjectVersionsPath) {
    send(res, [
      {
        schedule_version_key: version,
        display_label: health.current_schedule.display_label,
        activity_count: health.current_schedule.activity_count,
      },
    ])
    return
  }
  if (url.pathname.endsWith('/health-data')) {
    send(res, health)
    return
  }
  if (url.pathname.endsWith('/quality')) {
    send(res, quality)
    return
  }

  send(res, { detail: 'not_found', path: url.pathname }, 404)
})

server.listen(8000, '127.0.0.1', () => {
  console.log(`mock health API listening on http://127.0.0.1:8000 for ${version}`)
})
