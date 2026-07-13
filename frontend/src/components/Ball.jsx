const sizes = {
  sm: 'w-7 h-7 text-xs',
  md: 'w-9 h-9 text-sm',
  lg: 'w-11 h-11 text-base',
}

export default function Ball({ n, size = 'md', muted = false, highlight = false }) {
  const color = highlight
    ? 'bg-amber-500 text-white'
    : muted
      ? 'bg-zinc-200 text-zinc-600'
      : 'bg-emerald-600 text-white'
  return (
    <span
      className={`${sizes[size]} ${color} rounded-full inline-flex items-center justify-center font-bold tabular-nums shrink-0`}
    >
      {String(n).padStart(2, '0')}
    </span>
  )
}

export function BallRow({ dezenas, size = 'md', highlightSet }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {dezenas.map((d) => (
        <Ball key={d} n={d} size={size} highlight={highlightSet?.has(d)} />
      ))}
    </div>
  )
}
