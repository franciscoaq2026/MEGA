const ITEMS = [
  ['soma', 'soma'],
  ['pares', 'P'],
  ['primos', 'primos'],
  ['moldura', 'moldura'],
  ['consecutivos', 'seq'],
]

export default function MetricBadges({ m }) {
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {ITEMS.map(([k, label]) => (
        <span
          key={k}
          className="text-[10px] bg-zinc-100 text-zinc-600 rounded px-1.5 py-0.5 tabular-nums"
        >
          {label} {m[k]}
        </span>
      ))}
      {m.repetidas_anterior != null && (
        <span className="text-[10px] bg-zinc-100 text-zinc-600 rounded px-1.5 py-0.5 tabular-nums">
          rep {m.repetidas_anterior}
        </span>
      )}
    </div>
  )
}
