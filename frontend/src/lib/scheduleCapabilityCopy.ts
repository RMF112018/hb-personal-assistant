export type ScheduleSourceFormat =
  | 'primavera_pmxml'
  | 'primavera_xer'
  | 'ms_project_xml'
  | 'procore_json'
  | 'csv'
  | string

export function getScheduleFormatLabel(format: ScheduleSourceFormat | undefined): string {
  switch (format) {
    case 'primavera_pmxml':
      return 'P6 API XML'
    case 'primavera_xer':
      return 'Primavera XER'
    case 'ms_project_xml':
      return 'MSP XML'
    case 'procore_json':
      return 'Procore API'
    case 'csv':
      return 'CSV'
    default:
      return format ?? 'Unknown'
  }
}

export function getScheduleCapabilityBanner(format: ScheduleSourceFormat | undefined): string {
  switch (format) {
    case 'primavera_pmxml':
      return 'P6 API XML: partial critical-float only (derived finish float; no authoritative driving path)'
    case 'primavera_xer':
      return 'XER: source critical path basis varies by export (CT_DrivPath vs CT_TotFloat); DCMA Check 12 requires CPM recalculation'
    case 'ms_project_xml':
      return 'MSP XML: MSP critical/slack fields available when exported'
    default:
      return 'Schedule source capability varies by export format'
  }
}

export const CPM_RECALCULATION_BANNER = 'CPM recalculation: not implemented'

export function formatProjectCapabilityBanner(
  projectLabel: string | undefined,
  projectKey: string | undefined,
  format: ScheduleSourceFormat | undefined,
): string {
  const project = projectLabel || projectKey || 'selected project'
  return `For ${project}: ${getScheduleCapabilityBanner(format)}`
}