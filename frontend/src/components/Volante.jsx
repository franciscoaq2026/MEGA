export default function Volante({ selected, onChange, max = 6 }) {
  const set = new Set(selected)

  function toggle(n) {
    if (set.has(n)) {
      onChange(selected.filter((x) => x !== n))
    } else if (selected.length < max) {
      onChange([...selected, n].sort((a, b) => a - b))
    }
  }

  return (
    <div className="grid grid-cols-10 gap-1 max-w-md">
      {Array.from({ length: 60 }, (_, i) => i + 1).map((n) => {
        const on = set.has(n)
        return (
          <button
            key={n}
            type="button"
            onClick={() => toggle(n)}
            aria-pressed={on}
            className={`w-9 h-9 rounded-full text-xs font-bold tabular-nums transition-colors ${
              on
                ? 'bg-emerald-600 text-white'
                : 'bg-white border border-zinc-300 text-zinc-700 hover:border-emerald-500 hover:text-emerald-700'
            }`}
          >
            {String(n).padStart(2, '0')}
          </button>
        )
      })}
    </div>
  )
}
