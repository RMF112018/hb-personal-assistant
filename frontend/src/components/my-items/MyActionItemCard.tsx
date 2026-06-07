
export function MyActionItemCard({ title, source, age, project, review }: { title: string; source?: string; age?: string; project?: string; review?: boolean }) {
  const meta = [project || source, age].filter(Boolean).join(' • ')
  return (
    <div className="card text-sm flex justify-between">
      <span>{title}{review ? ' (review)' : ''}</span>
      {meta && <span className="text-xs text-[var(--hb-muted)]">{meta}</span>}
    </div>
  )
}
