import React from 'react'

interface ErrorBoundaryState {
  hasError: boolean
  error?: Error | null
}

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallbackMessage?: string
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log for developers; do not surface raw stack or details in the UI.
    // CM-first: friendly advisory only.
    // eslint-disable-next-line no-console
    console.error('App render error (ErrorBoundary):', error, errorInfo)
  }

  handleReload = () => {
    // Simple, reliable recovery for local dev / operator.
    if (typeof window !== 'undefined') {
      window.location.reload()
    }
  }

  render() {
    if (this.state.hasError) {
      const msg = this.props.fallbackMessage || 'Something went wrong rendering this view. All signals advisory. Try reloading.'
      return (
        <div className="p-6">
          <div className="text-sm text-[var(--hb-muted)] mb-2">{msg}</div>
          <button
            type="button"
            className="badge"
            onClick={this.handleReload}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
