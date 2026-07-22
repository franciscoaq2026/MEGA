import { useLottery } from '../lib/LotteryContext.jsx'

// Volante parametrizado pela loteria atual (intervalo de números e grade).
// `max` é o limite de dezenas selecionáveis (default: a aposta simples da loteria).
export default function Volante({ selected, onChange, max }) {
  const { cfg } = useLottery()
  const limit = max ?? cfg.escolher
  const set = new Set(selected)
  const numbers = Array.from({ length: cfg.total }, (_, i) => cfg.min + i)

  function toggle(n) {
    if (set.has(n)) {
      onChange(selected.filter((x) => x !== n))
    } else if (selected.length < limit) {
      onChange([...selected, n].sort((a, b) => a - b))
    }
  }

  return (
    <div className={`grid grid-cols-10 gap-1 ${cfg.total > 60 ? 'max-w-lg' : 'max-w-md'}`}>
      {numbers.map((n) => {
        const on = set.has(n)
        return (
          <button
            key={n}
            type="button"
            onClick={() => toggle(n)}
            aria-pressed={on}
            className={`w-8 h-8 sm:w-9 sm:h-9 rounded-full text-xs font-bold tabular-nums transition-colors ${
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
