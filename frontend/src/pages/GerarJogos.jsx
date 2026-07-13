import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import { formatMoney } from '../lib/format.js'

const ESTRATEGIAS = [
  {
    id: 'aleatorio',
    nome: 'Aleatório puro',
    desc: 'Sem viés nenhum — exatamente como a loteria funciona (baseline).',
  },
  {
    id: 'frequencia',
    nome: 'Frequência histórica',
    desc: 'Números mais sorteados no passado recebem mais peso.',
  },
  {
    id: 'atrasados',
    nome: 'Atrasados',
    desc: 'Prioriza números que não saem há mais concursos.',
  },
  {
    id: 'balanceado',
    nome: 'Balanceado',
    desc: 'Mistura quentes e frios, equilibra pares/ímpares e mira a soma perto da média histórica (~183).',
  },
]

const fmt = (n) => (n == null ? '—' : n.toLocaleString('pt-BR'))

export default function GerarJogos() {
  const [estrategia, setEstrategia] = useState('aleatorio')
  const [qtdJogos, setQtdJogos] = useState(3)
  const [dezenas, setDezenas] = useState(6)
  const [antiRateio, setAntiRateio] = useState(false)
  const [preco, setPreco] = useState('6.00')
  const [odds, setOdds] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const precoNum = Number.parseFloat(preco.replace(',', '.')) || 0
    apiGet(`/odds?dezenas=${dezenas}&preco_simples=${precoNum}`)
      .then(setOdds)
      .catch(() => setOdds(null))
  }, [dezenas, preco])

  async function gerar() {
    setBusy(true)
    setError(null)
    try {
      const r = await apiPost('/generate', {
        estrategia,
        jogos: qtdJogos,
        dezenas,
        anti_rateio: antiRateio,
      })
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Gerar jogos</h2>

      <div className="grid lg:grid-cols-3 gap-4 items-start">
        <Card title="Estratégia" className="lg:col-span-2">
          <div className="grid sm:grid-cols-2 gap-2">
            {ESTRATEGIAS.map((e) => (
              <label
                key={e.id}
                className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                  estrategia === e.id
                    ? 'border-emerald-600 bg-emerald-50'
                    : 'border-zinc-200 hover:border-emerald-300'
                }`}
              >
                <input
                  type="radio"
                  name="estrategia"
                  value={e.id}
                  checked={estrategia === e.id}
                  onChange={() => setEstrategia(e.id)}
                  className="sr-only"
                />
                <p className="font-medium text-sm">{e.nome}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{e.desc}</p>
              </label>
            ))}
          </div>

          <div className="grid sm:grid-cols-3 gap-4 mt-4">
            <label className="text-sm">
              <span className="text-zinc-600">Quantos jogos</span>
              <input
                type="number"
                min="1"
                max="20"
                value={qtdJogos}
                onChange={(e) => setQtdJogos(Math.min(20, Math.max(1, Number(e.target.value))))}
                className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5"
              />
            </label>
            <label className="text-sm">
              <span className="text-zinc-600">Dezenas por jogo (6–15)</span>
              <select
                value={dezenas}
                onChange={(e) => setDezenas(Number(e.target.value))}
                className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 bg-white"
              >
                {Array.from({ length: 10 }, (_, i) => 6 + i).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-start gap-2 text-sm sm:mt-6">
              <input
                type="checkbox"
                checked={antiRateio}
                onChange={(e) => setAntiRateio(e.target.checked)}
                className="mt-0.5 accent-emerald-600"
              />
              <span>
                <span className="text-zinc-800 font-medium">Anti-rateio</span>
                <span className="block text-xs text-zinc-500">
                  Evita combinações populares (só datas, sequências, desenhos). Não muda a chance
                  de ganhar — mas, se ganhar, divide com menos gente.
                </span>
              </span>
            </label>
          </div>

          <button
            onClick={gerar}
            disabled={busy}
            className="mt-4 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
          >
            {busy ? 'Gerando…' : `Gerar ${qtdJogos} jogo(s)`}
          </button>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </Card>

        <Card
          title="Probabilidades reais"
          subtitle={`Jogo de ${dezenas} dezenas — matemática exata, igual para qualquer escolha de números`}
        >
          {odds ? (
            <div className="space-y-3 text-sm">
              <table className="w-full text-left">
                <tbody>
                  {[
                    ['Sena (6 acertos)', odds.faixas.sena.one_in],
                    ['Quina (5 acertos)', odds.faixas.quina.one_in],
                    ['Quadra (4 acertos)', odds.faixas.quadra.one_in],
                  ].map(([label, oneIn]) => (
                    <tr key={label} className="border-b border-zinc-100 last:border-0">
                      <td className="py-1.5 text-zinc-600">{label}</td>
                      <td className="py-1.5 text-right font-semibold tabular-nums">
                        1 em {fmt(oneIn)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-zinc-500">
                {dezenas} dezenas = <strong>{fmt(odds.combos_simples)}</strong> jogo(s) simples.
              </p>
              <label className="flex items-center gap-2 text-xs text-zinc-600">
                Preço da aposta simples: R$
                <input
                  value={preco}
                  onChange={(e) => setPreco(e.target.value)}
                  className="w-16 border border-zinc-300 rounded px-1.5 py-1 text-right"
                  inputMode="decimal"
                />
              </label>
              <p className="text-xs text-zinc-600">
                Custo estimado por jogo:{' '}
                <strong className="text-emerald-700">{formatMoney(odds.custo_estimado)}</strong>
              </p>
              <p className="text-xs text-zinc-500 border-t border-zinc-100 pt-2">
                A única forma real de aumentar a chance é jogar mais combinações (2 jogos = 2× a
                chance) — é assim que os bolões de lotérica “ganham sempre”: volume, não segredo.
              </p>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Carregando…</p>
          )}
        </Card>
      </div>

      {result && (
        <Card
          title={`Jogos gerados — ${ESTRATEGIAS.find((e) => e.id === result.estrategia)?.nome}`}
          subtitle={result.aviso}
        >
          <div className="grid sm:grid-cols-2 gap-3">
            {result.jogos.map((j, i) => (
              <div key={i} className="border border-zinc-200 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-zinc-500">Jogo {i + 1}</span>
                  <span className="text-xs text-zinc-500">
                    soma {j.soma} · {j.pares}P/{j.dezenas.length - j.pares}Í
                  </span>
                </div>
                <BallRow dezenas={j.dezenas} size="sm" />
                {j.padroes_populares.length > 0 && (
                  <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-2">
                    ⚠️ Combinação popular: {j.padroes_populares.join('; ')} — em caso de prêmio,
                    tende a dividir com mais gente.
                  </p>
                )}
              </div>
            ))}
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            Na etapa “Meus jogos” você poderá salvar um jogo gerado e vinculá-lo a um concurso.
          </p>
        </Card>
      )}
    </div>
  )
}
