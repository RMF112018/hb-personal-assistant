export type ErrorCopy = {
  userMessage: string
  technicalDetail?: string
  title?: string
  message?: string
  detail?: string
  code?: string
  status?: number
}

const GENERIC_LOAD_MESSAGE = 'We could not load this section.'
const DETAILS_UNAVAILABLE = 'Details unavailable'

const KNOWN_ERROR_COPY: Record<string, string> = {
  invalid_ui_role: 'You do not have access to this view.',
  not_found: 'This information is not available yet.',
  schedule_not_found: 'This information is not available yet.',
  source_not_found: 'This information is not available yet.',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function cleanString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

function extractStatus(error: unknown): number | undefined {
  if (!isRecord(error)) return undefined
  const status = error.status ?? error.statusCode
  return typeof status === 'number' ? status : undefined
}

function extractCode(error: unknown): string | undefined {
  if (typeof error === 'string') return cleanString(error)

  if (!isRecord(error)) return undefined

  const direct = cleanString(error.code)
  if (direct) return direct

  if (isRecord(error.detail)) {
    const detailCode = cleanString(error.detail.code)
    if (detailCode) return detailCode
  }

  const detailString = cleanString(error.detail)
  if (detailString && detailString in KNOWN_ERROR_COPY) return detailString

  return undefined
}

function extractTechnicalDetail(error: unknown): string | undefined {
  if (error instanceof Error) return cleanString(error.message)

  if (typeof error === 'string') return cleanString(error)

  if (!isRecord(error)) return undefined

  const candidates = [
    error.technicalDetail,
    error.detail,
    error.message,
    error.error,
    error.code,
  ]

  for (const candidate of candidates) {
    const text = cleanString(candidate)
    if (text) return text
  }

  return undefined
}

export function safeDisplayText(value: unknown, fallback = DETAILS_UNAVAILABLE): string {
  if (value === null || value === undefined) return fallback

  const direct = cleanString(value)
  if (direct) return direct

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  if (value instanceof Error) {
    return cleanString(value.message) ?? fallback
  }

  if (Array.isArray(value)) {
    const rendered = value
      .map((item) => safeDisplayText(item, ''))
      .filter(Boolean)
      .join(', ')
    return rendered || fallback
  }

  if (isRecord(value)) {
    for (const key of ['title', 'userMessage', 'message', 'name', 'label']) {
      const candidate = cleanString(value[key])
      if (candidate) return candidate
    }
    return fallback
  }

  return fallback
}

export function getErrorCopy(error: unknown): ErrorCopy {
  const status = extractStatus(error)
  const code = extractCode(error)
  const technicalDetail = extractTechnicalDetail(error)

  let userMessage = GENERIC_LOAD_MESSAGE

  if (code && KNOWN_ERROR_COPY[code]) {
    userMessage = KNOWN_ERROR_COPY[code]
  } else if (status === 404) {
    userMessage = KNOWN_ERROR_COPY.not_found
  } else if (typeof error === 'string' && KNOWN_ERROR_COPY[error]) {
    userMessage = KNOWN_ERROR_COPY[error]
  }

  return {
    userMessage,
    technicalDetail,
    title: userMessage,
    message: userMessage,
    detail: technicalDetail,
    code,
    status,
  }
}
