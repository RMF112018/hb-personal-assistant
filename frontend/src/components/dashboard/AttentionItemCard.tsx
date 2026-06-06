
export function AttentionItemCard({ title, when, project }: { title: string; when: string; project?: string }) {
  return (
    <div className="card flex justify-between gap-2 text-sm">
      <div>
        <div>{title}</div>
        {project && <div className="text-xs text-[var(--hb-muted)]">{project}</div>}
      </div>
      <div className="text-xs text-[var(--hb-muted)] whitespace-nowrap">{when}</div>
    </div>
  )
}
