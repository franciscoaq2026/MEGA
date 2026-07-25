import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'
import { addBet } from '../lib/bets.js'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import Help from '../components/Help.jsx'
import Volante from '../components/Volante.jsx'
import MetricBadges from '../components/MetricBadges.jsx'
import { formatMoney, formatNumber } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'

const TABS = [
  ['gerador', '🎛️ Gerador avançado'],
  ['fechamento', '🔗 Fechamento'],
  ['termometro', '🌡️ Termômetro'],
]

// Catálogo de filtros. A faixa típica de cada um vem do histórico REAL da
// loteria (endpoint /analysis/ranges), então os textos não citam números fixos.
const FILTROS_BASE = {
  soma: ['Soma das dezenas', 'A soma dos números do jogo. A faixa típica abaixo é calculada do histórico real desta loteria. Descarta jogos fora do intervalo que você definir — é cosmético, não muda a chance.'],
  pares: ['Quantidade de pares', 'Quantos números pares o jogo tem. Só organiza a “cara” do jogo; não altera a probabilidade.'],
  primos: ['Números primos', 'Quantos primos (2, 3, 5, 7, 11, 13…) o jogo tem. Cosmético.'],
  moldura: ['Dezenas na moldura', 'Quantos números caem na borda do volante (primeira/última linha ou coluna). Puro padrão visual do cartão.'],
  miolo: ['Dezenas no miolo', 'Quantos números caem no centro do volante, fora da borda. No volante 5x5 da Lotofácil o miolo são só 9 dezenas (7, 8, 9, 12, 13, 14, 17, 18, 19). Cosmético.'],
  baixas: ['Dezenas baixas', 'Quantos números vêm da metade de baixo do volante. Serve para equilibrar baixas × altas. Cosmético.'],
  multiplos_3: ['Múltiplos de 3', 'Quantos números do jogo são divisíveis por 3. Cosmético.'],
  repetidas_anterior: ['Repetidas do último sorteio', 'Quantos números do seu jogo saíram no concurso anterior.'],
}

// Cada loteria filtra pelo que de fato discrimina nela. A Lotofácil ganha
// "miolo" e perde "consecutivos": marcar 15 de 25 força sequências em todo
// jogo (4+ seguidos saem em 87% dos sorteios), então o filtro não separaria nada.
const FILTROS_POR_LOTERIA = {
  mega: ['soma', 'pares', 'primos', 'moldura', 'baixas', 'multiplos_3', 'repetidas_anterior'],
  lofa: ['soma', 'pares', 'primos', 'moldura', 'miolo', 'baixas', 'multiplos_3', 'repetidas_anterior'],
}

// Ajuda específica que só faz sentido em uma loteria.
const AJUDA_POR_LOTERIA = {
  lofa: {
    repetidas_anterior:
      'Quantos números do seu jogo saíram no concurso anterior. Na Lotofácil este é o padrão mais estável da modalidade: como 15 das 25 dezenas saem a cada sorteio, tipicamente 9 se repetem do concurso anterior.',
  },
  mega: {
    repetidas_anterior:
      'Quantos números do seu jogo saíram no concurso anterior. Na Mega normalmente 0 ou 1 número se repete de um sorteio para o outro.',
  },
}

function filtrosDaLoteria(cfg) {
  const chaves = FILTROS_POR_LOTERIA[cfg.code] || FILTROS_POR_LOTERIA.mega
  const extra = AJUDA_POR_LOTERIA[cfg.code] || {}
  return chaves.map((k) => {
    const [label, help] = FILTROS_BASE[k]
    return [k, label, extra[k] || help]
  })
}

function parseDezenas(txt, cfg) {
  return [
    ...new Set(
      (txt.match(/\d+/g) || []).map(Number).filter((n) => n >= cfg.min && n <= cfg.max),
    ),
  ]
}

function useProximoConcurso() {
  const [concurso, setConcurso] = useState('')
  useEffect(() => {
    apiGet('/status')
      .then((st) => {
        const prox = st.proximo?.concurso ?? (st.ultimo_local ? st.ultimo_local.concurso + 1 : '')
        setConcurso((c) => c || prox)
      })
      .catch(() => {})
  }, [])
  return [concurso, setConcurso]
}

function SaveRow({ jogos, estrategia }) {
  const { code } = useLottery()
  const [concurso, setConcurso] = useProximoConcurso()
  const [salvos, setSalvos] = useState(false)
  return (
    <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-zinc-100">
      <span className="text-xs text-zinc-600">Salvar {jogos.length} jogo(s) no concurso</span>
      <input
        type="number"
        min="1"
        value={concurso}
        onChange={(e) => setConcurso(e.target.value)}
        className="w-24 border border-zinc-300 rounded-lg px-2 py-1 text-sm"
      />
      {salvos ? (
        <span className="text-xs text-emerald-700 font-medium">
          ✓ salvo —{' '}
          <Link to={`/${code}/meus-jogos`} className="underline">
            ver em Meus jogos
          </Link>
        </span>
      ) : (
        <button
          onClick={() => {
            if (!concurso) return
            jogos.forEach((dz) =>
              addBet({ loteria: code, concurso, origem: 'app', estrategia, dezenas: dz }),
            )
            setSalvos(true)
          }}
          disabled={!concurso}
          className="text-xs px-3 py-1.5 rounded-lg border border-emerald-600 text-emerald-700 font-medium hover:bg-emerald-50 disabled:opacity-50"
        >
          Salvar todos
        </button>
      )}
    </div>
  )
}

/* ----------------------------- Gerador avançado ----------------------------- */

function RangeFilter({ label, help, info, value, onChange }) {
  const on = value.enabled
  return (
    <div className={`border rounded-lg p-2.5 ${on ? 'border-emerald-300 bg-emerald-50/40' : 'border-zinc-200'}`}>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={on}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
          className="accent-emerald-600"
        />
        <span className="font-medium">{label}</span>
        {help && <Help text={help} />}
      </label>
      {info && (
        <p className="text-[11px] text-zinc-500 mt-0.5">
          típico: {info.p10}–{info.p90} · média {formatNumber(info.mean)}
        </p>
      )}
      {on && (
        <div className="flex items-center gap-1.5 mt-1.5">
          <input
            type="number"
            value={value.min}
            onChange={(e) => onChange({ ...value, min: e.target.value })}
            className="w-16 border border-zinc-300 rounded px-1.5 py-1 text-sm"
            placeholder="mín"
          />
          <span className="text-zinc-400 text-xs">até</span>
          <input
            type="number"
            value={value.max}
            onChange={(e) => onChange({ ...value, max: e.target.value })}
            className="w-16 border border-zinc-300 rounded px-1.5 py-1 text-sm"
            placeholder="máx"
          />
        </div>
      )}
    </div>
  )
}

function GeradorAvancado({ ranges }) {
  const { cfg } = useLottery()
  const FILTROS = useMemo(() => filtrosDaLoteria(cfg), [cfg])
  // Consecutivos só filtra onde discrimina (ver FILTROS_POR_LOTERIA).
  const usaConsecutivos = cfg.code === 'mega'
  const r = ranges?.ranges || {}
  const [dezenas, setDezenas] = useState(cfg.escolher)
  const [jogos, setJogos] = useState(5)
  const [antiRateio, setAntiRateio] = useState(true)
  const [consecMax, setConsecMax] = useState(3)
  const [incluir, setIncluir] = useState('')
  const [excluir, setExcluir] = useState('')
  const [filtros, setFiltros] = useState({})
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // defaults inteligentes vindos do histórico (p10–p90)
  useEffect(() => {
    if (!ranges) return
    const init = {}
    for (const [k] of FILTROS) {
      const info = r[k]
      init[k] = { enabled: false, min: info?.p10 ?? '', max: info?.p90 ?? '' }
    }
    setFiltros(init)
  }, [ranges]) // eslint-disable-line react-hooks/exhaustive-deps

  async function gerar() {
    setBusy(true)
    setError(null)
    try {
      const payload = {
        jogos,
        dezenas,
        anti_rateio: antiRateio,
        filtros: {},
        incluir: parseDezenas(incluir, cfg),
        excluir: parseDezenas(excluir, cfg),
      }
      for (const [k] of FILTROS) {
        const f = filtros[k]
        if (f?.enabled) payload.filtros[k] = { min: Number(f.min), max: Number(f.max) }
      }
      if (usaConsecutivos) payload.filtros.consecutivos_max = Number(consecMax)
      setResult(await apiPost('/generate-advanced', payload))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card
        title="Gerador com filtros avançados"
        subtitle="Gera apenas jogos que passam em TODOS os filtros ativos. Os defaults vêm da faixa típica do histórico."
      >
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {FILTROS.map(([k, label, help]) => (
            <RangeFilter
              key={k}
              label={label}
              help={help}
              info={r[k]}
              value={filtros[k] || { enabled: false, min: '', max: '' }}
              onChange={(v) => setFiltros((prev) => ({ ...prev, [k]: v }))}
            />
          ))}
          {usaConsecutivos && (
            <div className="border border-zinc-200 rounded-lg p-2.5">
              <p className="text-sm font-medium inline-flex items-center gap-1.5">
                Máx. de consecutivos
                <Help text="Limita sequências como 21-22-23. Ex.: “até 3 seguidos” evita jogos com muitos números em fila. Só afeta a aparência do jogo." />
              </p>
              <p className="text-[11px] text-zinc-500 mt-0.5">evita sequências longas</p>
              <select
                value={consecMax}
                onChange={(e) => setConsecMax(e.target.value)}
                className="mt-1.5 w-full border border-zinc-300 rounded px-1.5 py-1 text-sm bg-white"
              >
                {[2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    até {n} seguidos
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <label className="text-sm">
            <span className="text-zinc-600 inline-flex items-center gap-1.5">
              Dezenas fixas (sempre entram)
              <Help text="Números que você quer em TODOS os jogos gerados. Ex.: se você sempre joga o 7 e o 13, coloque-os aqui." />
            </span>
            <input
              value={incluir}
              onChange={(e) => setIncluir(e.target.value)}
              placeholder="ex: 7, 13"
              className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="text-zinc-600 inline-flex items-center gap-1.5">
              Dezenas excluídas (nunca entram)
              <Help text="Números que nunca devem aparecer nos jogos gerados. Ex.: números que você tem certeza de que não quer jogar." />
            </span>
            <input
              value={excluir}
              onChange={(e) => setExcluir(e.target.value)}
              placeholder={`ex: 4, 22, ${cfg.max}`}
              className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm"
            />
          </label>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 mt-3 items-end">
          <label className="text-sm">
            <span className="text-zinc-600 inline-flex items-center gap-1.5">
              Quantos jogos
              <Help text="Quantas apostas gerar que passem em TODOS os filtros marcados (1 a 50). Se os filtros forem muito apertados, ele pode gerar menos do que você pediu e avisa." />
            </span>
            <input
              type="number"
              min="1"
              max="50"
              value={jogos}
              onChange={(e) => setJogos(Math.min(50, Math.max(1, Number(e.target.value))))}
              className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5"
            />
          </label>
          <label className="text-sm">
            <span className="text-zinc-600 inline-flex items-center gap-1.5">
              Dezenas por jogo
              <Help text={`Tamanho de cada aposta (${cfg.escolher} a ${cfg.maxEscolher}). ${cfg.escolher} = aposta simples. Mais dezenas cobrem mais números e aumentam a chance de verdade, mas encarecem muito a aposta.`} />
            </span>
            <select
              value={dezenas}
              onChange={(e) => setDezenas(Number(e.target.value))}
              className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 bg-white"
            >
              {Array.from(
                { length: cfg.maxEscolher - cfg.escolher + 1 },
                (_, i) => cfg.escolher + i,
              ).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={antiRateio}
              onChange={(e) => setAntiRateio(e.target.checked)}
              className="accent-emerald-600"
            />
            <span className="inline-flex items-center gap-1.5">
              Anti-rateio
              <Help text="Descarta combinações muito populares (datas, sequências, desenhos). Não aumenta a chance de ganhar, mas se você ganhar, divide com menos gente." />
            </span>
          </label>
        </div>

        <button
          onClick={gerar}
          disabled={busy}
          className="mt-4 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy ? 'Gerando…' : 'Gerar jogos'}
        </button>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </Card>

      {result && (
        <Card
          title={`${result.gerados} jogo(s) gerado(s)`}
          subtitle={result.aviso}
        >
          {result.filtros_muito_restritivos && (
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
              ⚠️ Os filtros ficaram muito restritivos — consegui gerar {result.gerados} de{' '}
              {result.solicitados}. Afrouxe alguma faixa para conseguir mais.
            </p>
          )}
          <div className="grid sm:grid-cols-2 gap-3">
            {result.jogos.map((j, i) => (
              <div key={i} className="border border-zinc-200 rounded-lg p-3">
                <BallRow dezenas={j.dezenas} size="sm" />
                <MetricBadges m={j.metrics} />
                {j.padroes_populares.length > 0 && (
                  <p className="text-[11px] text-amber-700 mt-1">⚠️ {j.padroes_populares.join('; ')}</p>
                )}
              </div>
            ))}
          </div>
          {result.jogos.length > 0 && (
            <SaveRow jogos={result.jogos.map((j) => j.dezenas)} estrategia="avancado" />
          )}
        </Card>
      )}
    </div>
  )
}

/* ------------------------------- Fechamento ------------------------------- */

function Fechamento() {
  const { cfg } = useLottery()
  // Faixas que servem de garantia: todas abaixo do acerto máximo.
  const garantias = useMemo(
    () => cfg.premios.map((p) => p.ac).filter((ac) => ac < cfg.escolher).sort((a, b) => a - b),
    [cfg],
  )
  const minDezenas = cfg.escolher + 1
  const [dezenas, setDezenas] = useState([])
  const [tipo, setTipo] = useState('reduzida')
  const [garantia, setGarantia] = useState(garantias[garantias.length - 1])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function fechar() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await apiPost('/wheel', { dezenas, tipo, garantia }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card
        title="Fechamento / desdobramento"
        subtitle={`Escolha de ${minDezenas} a ${cfg.maxEscolher} dezenas. O app monta um conjunto de jogos com garantia matemática — e verifica a garantia antes de mostrar.`}
      >
        <Volante selected={dezenas} onChange={setDezenas} max={cfg.maxEscolher} />
        <p className="text-xs text-zinc-500 mt-2">{dezenas.length} dezenas selecionadas</p>

        <div className="grid sm:grid-cols-2 gap-3 mt-3">
          <label className="text-sm">
            <span className="text-zinc-600 inline-flex items-center gap-1.5">
              Tipo
              <Help text="Roda completa = TODAS as combinações possíveis das suas dezenas (garantia máxima, mas gera muitos jogos e custa caro). Reduzido = bem menos jogos, com uma garantia menor." />
            </span>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 bg-white"
            >
              <option value="reduzida">Reduzido (menos jogos, garantia menor)</option>
              <option value="completa">Roda completa (todos os jogos possíveis)</option>
            </select>
          </label>
          {tipo === 'reduzida' && (
            <label className="text-sm">
              <span className="text-zinc-600 inline-flex items-center gap-1.5">
                Garantia
                <Help text={`O prêmio garantido SE as ${cfg.sorteadas} dezenas sorteadas estiverem todas entre as que você escolheu. Atenção: não garante o prêmio máximo — garante cobertura das suas dezenas. Se as ${cfg.sorteadas} saírem entre as suas, um dos jogos com certeza terá pelo menos o número de acertos escolhido aqui.`} />
              </span>
              <select
                value={garantia}
                onChange={(e) => setGarantia(Number(e.target.value))}
                className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 bg-white"
              >
                {garantias.map((ac) => (
                  <option key={ac} value={ac}>
                    Garante {ac} acertos (se as {cfg.sorteadas} saírem entre as suas)
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <button
          onClick={fechar}
          disabled={busy || dezenas.length < minDezenas}
          className="mt-4 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy ? 'Montando…' : 'Montar fechamento'}
        </button>
        {dezenas.length > 0 && dezenas.length < minDezenas && (
          <p className="text-xs text-zinc-500 mt-2">
            selecione ao menos {minDezenas} dezenas (mais que a aposta simples)
          </p>
        )}
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </Card>

      {result && (
        <Card
          title={`${result.num_jogos} jogos · ${formatMoney(result.custo_estimado)}`}
          subtitle={
            result.tipo === 'reduzida'
              ? `Reduzido de ${formatNumber(result.num_jogos_roda_completa)} jogos da roda completa`
              : 'Roda completa (todas as combinações das suas dezenas)'
          }
        >
          {result.tipo === 'reduzida' ? (
            <div
              className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
                result.garantia_verificada
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-red-50 border-red-200 text-red-700'
              }`}
            >
              {result.garantia_verificada ? '✓' : '✗'} Garante ao menos{' '}
              <strong>{result.garantia_faixa.toUpperCase()}</strong> se as {cfg.sorteadas} dezenas
              sorteadas estiverem entre as suas {result.dezenas_escolhidas.length} escolhidas
              {result.garantia_verificada ? ' (garantia verificada por força bruta).' : '.'}
            </div>
          ) : (
            <div className="text-sm mb-3 space-y-1">
              {result.garantias.map((g) => (
                <p key={g.acertos_entre_suas} className="text-zinc-600">
                  ✓ {g.explicacao}
                </p>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className="text-xs text-zinc-500">Suas dezenas:</span>
            <BallRow dezenas={result.dezenas_escolhidas} size="sm" />
          </div>
          <div className="grid sm:grid-cols-2 gap-2 max-h-96 overflow-y-auto pr-1">
            {result.jogos.map((jogo, i) => (
              <div key={i} className="border border-zinc-200 rounded-lg p-2 flex items-center gap-2">
                <span className="text-[10px] text-zinc-400 w-6">{i + 1}</span>
                <BallRow dezenas={jogo} size="sm" />
              </div>
            ))}
          </div>
          <SaveRow jogos={result.jogos} estrategia={`fechamento-${result.tipo}`} />
        </Card>
      )}
    </div>
  )
}

/* ------------------------------- Termômetro ------------------------------- */

function Termometro() {
  const { cfg } = useLottery()
  const [dezenas, setDezenas] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function avaliar() {
    setBusy(true)
    setError(null)
    try {
      setResult(await apiPost('/score', { dezenas }))
    } catch (e) {
      setResult(null)
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const cor = (n) => (n >= 85 ? 'text-emerald-600' : n >= 65 ? 'text-emerald-500' : n >= 45 ? 'text-amber-500' : 'text-red-500')

  return (
    <div className="space-y-4">
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Termômetro de jogos
            <Help text="Cole um jogo (seu ou de qualquer fonte) e receba uma nota de 0 a 100 de quanto ele “se parece” com os sorteios típicos. IMPORTANTE: mede tipicidade/estética, NÃO chance de ganhar — um jogo nota 100 tem exatamente a mesma chance de um nota 10." />
          </span>
        }
        subtitle={`Selecione um jogo (${cfg.escolher} a ${cfg.maxEscolher} dezenas) e veja o quão dentro dos padrões históricos ele está. Mede tipicidade — não chance de ganhar.`}
      >
        <Volante selected={dezenas} onChange={setDezenas} max={cfg.maxEscolher} />
        <p className="text-xs text-zinc-500 mt-2">{dezenas.length} dezenas</p>
        <button
          onClick={avaliar}
          disabled={busy || dezenas.length < cfg.escolher}
          className="mt-3 px-5 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy ? 'Avaliando…' : 'Avaliar jogo'}
        </button>
        {dezenas.length > 0 && dezenas.length < cfg.escolher && (
          <p className="text-xs text-zinc-500 mt-2">
            selecione ao menos {cfg.escolher} dezenas
          </p>
        )}
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </Card>

      {result && (
        <Card title="Resultado" subtitle={result.aviso}>
          <div className="flex items-center gap-4 mb-4">
            <div className={`text-5xl font-bold tabular-nums ${cor(result.nota)}`}>{result.nota}</div>
            <div>
              <p className="text-sm font-medium">{result.classificacao}</p>
              <p className="text-xs text-zinc-500">nota de tipicidade (0–100)</p>
            </div>
          </div>
          <div className="space-y-1.5">
            {result.criterios.map((c) => (
              <div key={c.chave} className="flex items-center gap-2 text-sm">
                <span className="w-48 shrink-0 text-zinc-600">{c.label}</span>
                <span className="tabular-nums font-medium w-8 text-right">{c.valor}</span>
                <span className="text-xs text-zinc-400 w-24">
                  típico {c.faixa_tipica[0]}–{c.faixa_tipica[1]}
                </span>
                <div className="flex-1 h-2 bg-zinc-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${c.situacao === 'típico' ? 'bg-emerald-500' : 'bg-amber-400'}`}
                    style={{ width: `${c.pontos}%` }}
                  />
                </div>
                <span
                  className={`text-[10px] w-12 text-right ${c.situacao === 'típico' ? 'text-emerald-600' : 'text-amber-600'}`}
                >
                  {c.situacao}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

/* --------------------------------- Página --------------------------------- */

export default function Fabrica() {
  const { code } = useLottery()
  const [tab, setTab] = useState('gerador')
  const [ranges, setRanges] = useState(null)
  const [empty, setEmpty] = useState(false)

  useEffect(() => {
    apiGet('/analysis/ranges')
      .then(setRanges)
      .catch((e) => {
        if (String(e.message).includes('vazio') || String(e.message).includes('409')) setEmpty(true)
      })
  }, [])

  const conteudo = useMemo(() => {
    if (tab === 'gerador') return <GeradorAvancado ranges={ranges} />
    if (tab === 'fechamento') return <Fechamento />
    return <Termometro ranges={ranges} />
  }, [tab, ranges])

  if (empty) {
    return (
      <div className="bg-white border border-zinc-200 rounded-xl p-6">
        <h2 className="text-lg font-bold mb-1">Fábrica de números</h2>
        <p className="text-sm text-zinc-500">
          Sincronize os sorteios em{' '}
          <Link to={`/${code}/sorteios`} className="text-emerald-700 underline">
            Sorteios
          </Link>{' '}
          para liberar as ferramentas (elas usam o histórico).
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold">Fábrica de números</h2>
        <p className="text-xs text-zinc-500">
          As ferramentas avançadas. Diferente da aba <strong>Gerar jogos</strong> (rápida, escolhe
          uma estratégia e pronto), aqui você <strong>peneira por filtros</strong>, monta{' '}
          <strong>fechamentos</strong> com garantia e <strong>avalia</strong> jogos prontos. Nenhuma
          altera a chance de acerto — todo jogo tem a mesma.
        </p>
      </div>
      <div className="flex gap-1 flex-wrap">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
              tab === id
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'bg-white border-zinc-300 text-zinc-600 hover:border-emerald-400'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {conteudo}
    </div>
  )
}
