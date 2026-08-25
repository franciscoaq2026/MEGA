import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useLottery } from '../lib/LotteryContext.jsx'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet } from '../lib/api.js'
import Ball, { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import { formatDate, formatNumber } from '../lib/format.js'

const EMERALD = '#059669'
const BLUE = '#2563eb'
const GRID = '#e4e4e7'
const TICK = { fontSize: 11, fill: '#71717a' }
// Marcas do eixo X: de 5 em 5 dentro do volante da loteria (a Lotofácil vai
// só até 25, então a lista fixa de 1 a 60 da Mega não servia).
function ticksDoVolante(cfg) {
  const out = [cfg.min]
  for (let n = Math.ceil(cfg.min / 5) * 5; n <= cfg.max; n += 5) if (n !== cfg.min) out.push(n)
  if (out[out.length - 1] !== cfg.max) out.push(cfg.max)
  return out
}
const WINDOWS = [
  { value: 0, label: 'Todos' },
  { value: 100, label: 'Últimos 100' },
  { value: 50, label: 'Últimos 50' },
  { value: 25, label: 'Últimos 25' },
  { value: 10, label: 'Últimos 10' },
]

function Tip({ active, payload, label, render }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-zinc-200 rounded-lg px-2.5 py-1.5 text-xs shadow-sm">
      {render(label, payload)}
    </div>
  )
}

function Heatmap({ freq }) {
  const max = Math.max(1, ...freq.map((f) => f.count))
  return (
    <div>
      <div className="grid grid-cols-6 sm:grid-cols-10 gap-1">
        {freq.map(({ n, count }) => {
          const t = count / max
          return (
            <div
              key={n}
              title={`Nº ${n}: ${count}x`}
              className="rounded-md px-1 py-1.5 text-center"
              style={{ backgroundColor: `rgba(5, 150, 105, ${0.06 + 0.78 * t})` }}
            >
              <div className={`text-xs font-bold tabular-nums ${t > 0.55 ? 'text-white' : 'text-zinc-800'}`}>
                {String(n).padStart(2, '0')}
              </div>
              <div className={`text-[10px] tabular-nums ${t > 0.55 ? 'text-emerald-100' : 'text-zinc-500'}`}>
                {count}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function XRay({ defaultConcurso }) {
  const { cfg } = useLottery()
  // Acertos que o puro acaso entrega por jogo nesta loteria (0,6 na Mega; 9 na
  // Lotofácil) — a referência honesta para julgar "quentes" e "atrasados".
  const esperadoAcaso = (cfg.escolher * cfg.sorteadas) / cfg.total
  const [concurso, setConcurso] = useState(defaultConcurso)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const analyze = useCallback(async (n) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await apiGet(`/stats/xray/${n}`))
    } catch (e) {
      setResult(null)
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    if (defaultConcurso) analyze(defaultConcurso)
  }, [defaultConcurso, analyze])

  return (
    <Card
      title="Raio-X de um sorteio"
      subtitle="Onde cada dezena sorteada estava no ranking de frequência e atraso NA VÉSPERA do concurso — o teste honesto de “dava para prever?”"
    >
      <form
        className="flex gap-2 items-center mb-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (concurso) analyze(concurso)
        }}
      >
        <label className="text-sm text-zinc-600" htmlFor="xray-concurso">
          Concurso
        </label>
        <input
          id="xray-concurso"
          type="number"
          min="2"
          value={concurso ?? ''}
          onChange={(e) => setConcurso(Number(e.target.value))}
          className="w-28 border border-zinc-300 rounded-lg px-2 py-1.5 text-sm"
        />
        <button
          disabled={busy}
          className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
        >
          Analisar
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="space-y-4">
          <p className="text-sm text-zinc-600">
            Concurso <strong>{result.concurso}</strong> · {formatDate(result.data)} · analisado
            contra {result.prior_draws} sorteios anteriores · soma {result.soma} ·{' '}
            {result.pares} pares / {result.dezenas.length - result.pares} ímpares
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {result.dezenas.map((d) => (
              <div key={d.n} className="border border-zinc-200 rounded-lg p-2 text-center">
                <Ball n={d.n} size="md" />
                <p className="text-[11px] text-zinc-600 mt-1.5">
                  {d.freq_rank}º em frequência
                </p>
                <p className="text-[11px] text-zinc-500">
                  atraso: {d.delay_before} conc.
                </p>
              </div>
            ))}
          </div>
          <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3 space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-zinc-600 shrink-0">
                {cfg.escolher} mais quentes na véspera:
              </span>
              <BallRow dezenas={result.hot6} size="sm" highlightSet={new Set(result.dezenas.map((d) => d.n))} />
              <span className="font-semibold">
                → acertaram {result.hot6_matches} de {cfg.escolher}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-zinc-600 shrink-0">
                {cfg.escolher} mais atrasados na véspera:
              </span>
              <BallRow dezenas={result.overdue6} size="sm" highlightSet={new Set(result.dezenas.map((d) => d.n))} />
              <span className="font-semibold">
                → acertaram {result.overdue6_matches} de {cfg.escolher}
              </span>
            </div>
            <p className="text-xs text-zinc-500">
              Para referência: qualquer jogo fixo de {cfg.escolher} dezenas acerta, em média,{' '}
              {formatNumber(esperadoAcaso, 1)} dezena por sorteio — “quentes” e “atrasados” não
              fazem melhor que isso no longo prazo.
              (Dezenas em amarelo = coincidiram com o sorteio.)
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Estatisticas() {
  const { code, cfg } = useLottery()
  const numTicks = useMemo(() => ticksDoVolante(cfg), [cfg])
  // Atraso médio de um número: ele sai numa fração sorteadas/total dos
  // concursos, então espera-se total/sorteadas - 1 concursos entre aparições
  // (9 na Mega, 0,67 na Lotofácil — não dá para fixar o 9 da Mega nas duas).
  const atrasoEsperado = cfg.total / cfg.sorteadas - 1
  const [empty, setEmpty] = useState(false)
  const [error, setError] = useState(null)
  const [windowSize, setWindowSize] = useState(0)
  const [freq, setFreq] = useState(null)
  const [delay, setDelay] = useState(null)
  const [parity, setParity] = useState(null)
  const [sums, setSums] = useState(null)
  const [pairs, setPairs] = useState(null)
  const [ultimo, setUltimo] = useState(null)

  useEffect(() => {
    apiGet('/status')
      .then(async (st) => {
        if (st.total_draws === 0) {
          setEmpty(true)
          return
        }
        setUltimo(st.ultimo_local.concurso)
        const [d, p, s, pr] = await Promise.all([
          apiGet('/stats/delay'),
          apiGet('/stats/parity'),
          apiGet('/stats/sums'),
          apiGet('/stats/pairs?limit=15'),
        ])
        setDelay(d)
        setParity(p)
        setSums(s)
        setPairs(pr)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (empty) return
    apiGet(`/stats/frequency?window=${windowSize}`)
      .then(setFreq)
      .catch((e) => setError(e.message))
  }, [windowSize, empty])

  if (error) return <p className="text-sm text-red-600">{error}</p>

  if (empty) {
    return (
      <div className="bg-white border border-zinc-200 rounded-xl p-6">
        <h2 className="text-lg font-bold mb-1">Estatísticas</h2>
        <p className="text-sm text-zinc-500">
          O cache de sorteios está vazio. Vá em{' '}
          <Link to={`/${code}/sorteios`} className="text-emerald-700 font-medium underline">
            Sorteios
          </Link>{' '}
          e sincronize (ou importe um CSV) para liberar as análises.
        </p>
      </div>
    )
  }

  const maxPairCount = pairs?.pairs?.[0]?.count ?? 1

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Estatísticas</h2>
        <div className="flex gap-1 flex-wrap">
          {WINDOWS.map((w) => (
            <button
              key={w.value}
              onClick={() => setWindowSize(w.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                windowSize === w.value
                  ? 'bg-emerald-600 border-emerald-600 text-white'
                  : 'bg-white border-zinc-300 text-zinc-600 hover:border-emerald-400'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {freq && (
        <Card
          title="Frequência por número"
          subtitle={`${freq.draws_considered} concursos considerados · média esperada por número: ${formatNumber(freq.expected_per_number)}`}
        >
          <div className="overflow-x-auto">
            <div className="min-w-[720px] h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={freq.freq} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="n" ticks={numTicks} interval={0} tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} />
                  <YAxis tick={TICK} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                    content={
                      <Tip render={(label, pl) => `Nº ${String(label).padStart(2, '0')} — sorteado ${pl[0].value}x`} />
                    }
                  />
                  <ReferenceLine
                    y={freq.expected_per_number}
                    stroke="#a1a1aa"
                    strokeDasharray="4 4"
                  />
                  <Bar dataKey="count" fill={EMERALD} radius={[3, 3, 0, 0]} maxBarSize={10} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3 mt-4 text-sm">
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-1.5">🔥 Mais sorteados (quentes)</p>
              <div className="flex flex-wrap gap-1.5">
                {freq.hot.map((f) => (
                  <span key={f.n} className="inline-flex items-center gap-1">
                    <Ball n={f.n} size="sm" />
                    <span className="text-xs text-zinc-500">{f.count}</span>
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-1.5">🧊 Menos sorteados (frios)</p>
              <div className="flex flex-wrap gap-1.5">
                {freq.cold.map((f) => (
                  <span key={f.n} className="inline-flex items-center gap-1">
                    <Ball n={f.n} size="sm" muted />
                    <span className="text-xs text-zinc-500">{f.count}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {freq && (
        <Card
          title={`Mapa de calor ${cfg.min}–${cfg.max}`}
          subtitle="Quanto mais escuro, mais vezes o número foi sorteado na janela escolhida"
        >
          <Heatmap freq={freq.freq} />
        </Card>
      )}

      {delay && (
        <Card
          title="Atraso atual por número"
          subtitle={`Há quantos concursos cada número não é sorteado (0 = saiu no último) · linha tracejada: atraso esperado ≈ ${formatNumber(atrasoEsperado, 1)}`}
        >
          <div className="overflow-x-auto">
            <div className="min-w-[720px] h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={delay.delays} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="n" ticks={numTicks} interval={0} tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} />
                  <YAxis tick={TICK} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                    content={
                      <Tip
                        render={(label, pl) =>
                          `Nº ${String(label).padStart(2, '0')} — não sai há ${pl[0].value} concurso(s)`
                        }
                      />
                    }
                  />
                  <ReferenceLine y={atrasoEsperado} stroke="#a1a1aa" strokeDasharray="4 4" />
                  <Bar dataKey="delay" fill={EMERALD} radius={[3, 3, 0, 0]} maxBarSize={10} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-xs font-medium text-zinc-500 mb-1.5">⏳ Mais atrasados</p>
            <div className="flex flex-wrap gap-1.5">
              {delay.top.map((d) => (
                <span key={d.n} className="inline-flex items-center gap-1">
                  <Ball n={d.n} size="sm" />
                  <span className="text-xs text-zinc-500">{d.delay}</span>
                </span>
              ))}
            </div>
          </div>
        </Card>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        {parity && (
          <Card
            title="Pares vs. ímpares"
            subtitle={`Distribuição em ${parity.total_draws} sorteios, comparada com o esperado pelo puro acaso`}
          >
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={parity.rows.map((r) => ({ ...r, label: `${r.evens}P/${r.odds}Í` }))}
                  margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                >
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="label" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} />
                  <YAxis tick={TICK} tickLine={false} axisLine={false} unit="%" />
                  <Tooltip
                    cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                    content={
                      <Tip
                        render={(label, pl) => (
                          <div>
                            <p className="font-semibold">{label} (pares/ímpares)</p>
                            {pl.map((p) => (
                              <p key={p.dataKey}>
                                {p.name}: {p.value}%
                              </p>
                            ))}
                          </div>
                        )}
                      />
                    }
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />
                  <Bar name="Observado" dataKey="observed_pct" fill={EMERALD} radius={[3, 3, 0, 0]} maxBarSize={28} />
                  <Line
                    name="Esperado pelo acaso"
                    dataKey="theoretical_pct"
                    stroke={BLUE}
                    strokeWidth={2}
                    dot={{ r: 4, fill: BLUE, strokeWidth: 0 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}

        {sums && (
          <Card
            title="Soma das dezenas"
            subtitle={`Média observada: ${formatNumber(sums.mean)} · média teórica: ${formatNumber(sums.theoretical_mean)} · mín ${sums.min} / máx ${sums.max}`}
          >
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sums.bins} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="label" tick={{ ...TICK, fontSize: 9 }} tickLine={false} axisLine={{ stroke: GRID }} interval={1} angle={-35} textAnchor="end" height={40} />
                  <YAxis tick={TICK} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                    content={<Tip render={(label, pl) => `Soma ${label}: ${pl[0].value} sorteio(s)`} />}
                  />
                  <Bar dataKey="count" fill={EMERALD} radius={[3, 3, 0, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}
      </div>

      {pairs && (
        <Card
          title="Duplas que mais saem juntas"
          subtitle={`Aparições esperadas por dupla ao acaso: ~${formatNumber(pairs.expected_per_pair)} · as campeãs ficam pouco acima disso — flutuação normal`}
        >
          <div className="space-y-1.5">
            {pairs.pairs.map((p) => (
              <div key={`${p.a}-${p.b}`} className="flex items-center gap-2">
                <Ball n={p.a} size="sm" />
                <Ball n={p.b} size="sm" />
                <div className="flex-1 h-2.5 bg-zinc-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-600 rounded-full"
                    style={{ width: `${(100 * p.count) / maxPairCount}%` }}
                  />
                </div>
                <span className="text-xs text-zinc-600 tabular-nums w-8 text-right">{p.count}x</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {cfg.avancada && ultimo && <XRay defaultConcurso={ultimo} />}

      {!cfg.avancada && (
        <p className="text-xs text-zinc-500 border-t border-zinc-100 pt-3">
          O “Raio-X de um sorteio” (teste de previsibilidade) ainda não está disponível nesta
          loteria.
        </p>
      )}
    </div>
  )
}
