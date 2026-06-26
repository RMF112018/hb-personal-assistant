import type { ProjectSummary } from '../../lib/api'

export function projectDisplayName(project: ProjectSummary): string {
  return cleanProjectText(project.display_name) || project.project_key
}

export function formatProjectAddress(project: ProjectSummary): string {
  const address = cleanProjectText(project.address)
  const city = cleanProjectText(project.city)
  const state = cleanProjectText(project.state_code)
  const zip = cleanProjectText(project.zip)
  const region = [state, zip].filter(Boolean).join(' ')
  const locality = [city, region].filter(Boolean).join(', ')

  if (address && locality) return `${address} · ${locality}`
  if (address) return address
  if (locality) return locality
  return 'Address not available'
}

export function cleanProjectText(value: string | null | undefined): string | null {
  const text = value?.trim()
  return text || null
}
