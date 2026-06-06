
export function MyActionItemCard({ title, source, age }: { title: string; source: string; age: string }) {
  return <div className="card text-sm flex justify-between"><span>{title}</span><span className="text-xs text-[var(--hb-muted)]">{source} • {age}</span></div>
}
