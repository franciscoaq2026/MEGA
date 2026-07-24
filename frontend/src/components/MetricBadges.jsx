import { useLottery } from '../lib/LotteryContext.jsx'

// Indicadores mostrados por loteria — os mesmos que o backend pontua.
// A Lotofácil mostra "miolo" no lugar de "seq": marcar 15 de 25 força
// sequências em todo jogo, então o número não diz nada ali.
const ITEMS_POR_LOTERIA = {
  mega: [
    ['soma', 'soma'],
    ['pares', 'P'],
    ['primos', 'primos'],
    ['moldura', 'moldura'],
    ['consecutivos', 'seq'],
  ],
  lofa: [
    ['soma', 'soma'],
    ['pares', 'P'],
    ['primos', 'primos'],
    ['moldura', 'moldura'],
    ['miolo', 'miolo'],
  ],
}

export default function MetricBadges({ m }) {
  const { cfg } = useLottery()
  const items = ITEMS_POR_LOTERIA[cfg.code] || ITEMS_POR_LOTERIA.mega
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {items.map(([k, label]) => (
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
