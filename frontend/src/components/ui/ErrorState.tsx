export function ErrorState({ message, onRetry, className }: { message: string | null; onRetry?: () => void; className?: string }) {
  if (!message) return null
  return (
    <div className={`text-xs text-red-500 ${className || ''}`}>
      {message}
      {onRetry && (
        <button className="badge ml-2" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
