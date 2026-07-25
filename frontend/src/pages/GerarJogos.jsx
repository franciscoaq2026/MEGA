import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'
import { addBet } from '../lib/bets.js'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import Help from '../components/Help.jsx'
import { formatMoney } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'

// Descrições genéricas: valem para qualquer loteria do hub. O que é
// específico (soma média, tamanho da aposta) vem da config em tempo de render.
const ESTRATEGIAS = [
  {
    id: 'aleatorio',
    nome: 'Aleatório puro',
    desc: 'Sem viés nenhum — exatamente como a loteria funciona (baseline).',
    help: 'Sorteia os números totalmente ao acaso, igual ao sorteio de verdade. É a opção mais honesta: nenhuma outra estratégia tem chance de acerto maior do que esta.',
  },
  {
    id: 'frequencia',
    nome: 'Frequência histórica',
    desc: 'Números mais sorteados no passado recebem mais peso.',
    help: 'Dá preferência aos números que mais saíram no histórico (os “quentes”). Parece esperto, mas NÃO aumenta a chance — a bolinha não lembra do passado. Serve para quem gosta de apostar nos mais frequentes.',
  },
  {
    id: 'atrasados',
    nome: 'Atrasados',
    desc: 'Prioriza números que não saem há mais concursos.',
    help: 'Dá preferência aos números que estão há mais tempo sem sair (a ideia de “já vai sair”). É a ilusão oposta à da frequência; também não muda a chance real.',
  },
  {
    id: 'balanceado',
    nome: 'Balanceado',
    desc: 'Mistura quentes e frios, equilibra pares/ímpares e mira a soma perto da média histórica.',
    help: 'Monta jogos parecidos com os sorteios típicos: mistura quentes e frios, equilibra pares/ímpares e mira a soma perto da média da loteria. Dá cara de “jogo bem-feito”, mas não altera a probabilidade.',
  },
]

const fmt = (n) => (n == null ? '—' : n.toLocaleString('pt-BR'))

export default function GerarJogos() {
  const { code, cfg } = useLottery()
  const dezenasFixas = cfg.escolher === cfg.maxEscolher
  // Formato da aposta. 'simples' = N bilhetes de escolher dezenas, comprados
  // separados. 'multipla' = UM bilhete com mais dezenas (o fechamento).
  const [formato, setFormato] = useState('simples')
  const simples = formato === 'simples'
  const [estrategia, setEstrategia] = useState('aleatorio')
  const [qtdJogos, setQtdJogos] = useState(3)
  const [dezenas, setDezenas] = useState(cfg.escolher)
  const [antiRateio, setAntiRateio] = useState(false)
  const [espalhar, setEspalhar] = useState(true)
  const [preco, setPreco] = useState(cfg.preco.toFixed(2))
  const [odds, setOdds] = useState(null)
  const [carteira, setCarteira] = useState(null)
  // Chance de levar algo com o MESMO dinheiro em bilhetes simples separados.
  const equivalente = odds?.equivalente_simples
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [concursoSalvar, setConcursoSalvar] = useState('')
  const [salvos, setSalvos] = useState({}) // índice do jogo -> concurso salvo
  const [backtest, setBacktest] = useState(null)
  const [backtestBusy, setBacktestBusy] = useState(false)
  const [backtestError, setBacktestError] = useState(null)

  useEffect(() => {
    apiGet('/status')
      .then((st) => {
        const prox = st.proximo?.concurso ?? (st.ultimo_local ? st.ultimo_local.concurso + 1 : '')
        setConcursoSalvar((c) => c || prox)
      })
      .catch(() => {})
  }, [])

  // Ao trocar de formato, o tamanho da aposta acompanha: simples volta para a
  // aposta mínima; múltipla começa uma dezena acima dela.
  useEffect(() => {
    setDezenas(simples ? cfg.escolher : Math.min(cfg.escolher + 1, cfg.maxEscolher))
  }, [formato, cfg.escolher, cfg.maxEscolher, simples])

  useEffect(() => {
    if (!cfg.avancada) {
      setOdds(null)
      return
    }
    const precoNum = Number.parseFloat(preco.replace(',', '.')) || 0
    apiGet(`/odds?dezenas=${dezenas}&preco_simples=${precoNum}`)
      .then(setOdds)
      .catch(() => setOdds(null))
  }, [dezenas, preco, cfg.avancada])

  // Chance acumulada de N bilhetes simples separados — a conta que interessa
  // a quem joga simples, e a base da comparação com a aposta múltipla.
  useEffect(() => {
    apiGet(`/odds/carteira?jogos=${qtdJogos}`)
      .then(setCarteira)
      .catch(() => setCarteira(null))
  }, [qtdJogos])

  function salvar(i, jogo) {
    if (!concursoSalvar) return
    addBet({
      loteria: code,
      concurso: concursoSalvar,
      origem: 'app',
      estrategia: result.estrategia,
      dezenas: jogo.dezenas,
    })
    setSalvos((s) => ({ ...s, [i]: concursoSalvar }))
  }

  async function rodarBacktest() {
    setBacktestBusy(true)
    setBacktestError(null)
    try {
      setBacktest(await apiPost('/backtest?ultimos=100'))
    } catch (e) {
      setBacktestError(e.message)
    } finally {
      setBacktestBusy(false)
    }
  }

  async function gerar() {
    setBusy(true)
    setError(null)
    try {
      const r = await apiPost('/generate', {
        estrategia,
        jogos: simples ? qtdJogos : 1,
        dezenas,
        anti_rateio: antiRateio,
        espalhar: simples && espalhar,
      })
      setResult(r)
      setSalvos({})
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold">Gerar jogos</h2>
        <p className="text-xs text-zinc-500">
          Escolha o formato da aposta, diga quantos jogos e gere. As probabilidades ao lado
          acompanham a sua escolha. Para peneirar por soma, pares, primos etc., use a aba{' '}
          <strong>Fábrica</strong>.
        </p>
      </div>

      {/* Formato: a decisão que mais muda o resultado prático */}
      {!dezenasFixas && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              Formato da aposta
              <Help text="Bilhetes simples separados e uma aposta múltipla do mesmo valor têm a MESMA chance no prêmio principal. O que muda é a chance de levar algum prêmio: bilhetes separados se espalham e cobrem situações diferentes; a aposta múltipla concentra, ganhando mais raramente porém em várias faixas de uma vez." />
            </span>
          }
        >
          <div className="grid sm:grid-cols-2 gap-2">
            {[
              {
                id: 'simples',
                nome: `Jogos simples separados`,
                desc: `Vários bilhetes de ${cfg.escolher} dezenas, comprados um a um. Maior chance de levar algum prêmio pelo mesmo dinheiro.`,
              },
              {
                id: 'multipla',
                nome: 'Uma aposta múltipla',
                desc: `Um único bilhete com mais de ${cfg.escolher} dezenas. Mesmo prêmio principal, mas concentra: ganha menos vezes e em bloco.`,
              },
            ].map((f) => (
              <label
                key={f.id}
                className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                  formato === f.id
                    ? 'border-emerald-600 bg-emerald-50'
                    : 'border-zinc-200 hover:border-emerald-300'
                }`}
              >
                <input
                  type="radio"
                  name="formato"
                  value={f.id}
                  checked={formato === f.id}
                  onChange={() => setFormato(f.id)}
                  className="sr-only"
                />
                <p className="font-medium text-sm">{f.nome}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{f.desc}</p>
              </label>
            ))}
          </div>
        </Card>
      )}

      <div className={`grid gap-4 items-start ${cfg.avancada ? 'lg:grid-cols-3' : ''}`}>
        <Card title="Estratégia" className={cfg.avancada ? 'lg:col-span-2' : ''}>
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
                <p className="font-medium text-sm flex items-center gap-1.5">
                  {e.nome}
                  <Help text={e.help} />
                </p>
                <p className="text-xs text-zinc-500 mt-0.5">{e.desc}</p>
              </label>
            ))}
          </div>

          <div className="grid sm:grid-cols-3 gap-4 mt-4">
            {simples ? (
              <label className="text-sm">
                <span className="text-zinc-600 inline-flex items-center gap-1.5">
                  Quantos jogos
                  <Help text="Quantos bilhetes simples separados gerar (1 a 20). Cada bilhete a mais aumenta a sua chance de verdade, na proporção do que custa: 2 jogos = 2x a chance do prêmio principal." />
                </span>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={qtdJogos}
                  onChange={(e) => setQtdJogos(Math.min(20, Math.max(1, Number(e.target.value))))}
                  className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5"
                />
                <span className="block text-[11px] text-zinc-500 mt-1">
                  {cfg.escolher} dezenas cada · {formatMoney(qtdJogos * cfg.preco)}
                </span>
              </label>
            ) : (
              <label className="text-sm">
                <span className="text-zinc-600 inline-flex items-center gap-1.5">
                  Dezenas no bilhete ({cfg.escolher + 1}–{cfg.maxEscolher})
                  <Help text="Tamanho da aposta múltipla. Cada dezena a mais multiplica o número de combinações cobertas — e o preço na mesma medida. Veja o custo ao lado antes de decidir." />
                </span>
                <select
                  value={dezenas}
                  onChange={(e) => setDezenas(Number(e.target.value))}
                  className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5 bg-white"
                >
                  {Array.from(
                    { length: cfg.maxEscolher - cfg.escolher },
                    (_, i) => cfg.escolher + 1 + i,
                  ).map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
                <span className="block text-[11px] text-zinc-500 mt-1">
                  1 bilhete · {odds ? formatMoney(odds.custo_estimado) : '…'}
                </span>
              </label>
            )}
            {simples && qtdJogos > 1 ? (
              <label className="flex items-start gap-2 text-sm sm:mt-6">
                <input
                  type="checkbox"
                  checked={espalhar}
                  onChange={(e) => setEspalhar(e.target.checked)}
                  className="mt-0.5 accent-emerald-600"
                />
                <span>
                  <span className="text-zinc-800 font-medium inline-flex items-center gap-1.5">
                    Espalhar os jogos
                    <Help text="Faz os seus bilhetes serem diferentes entre si, em vez de quase iguais. Medido por enumeração exata dos 3.268.760 sorteios da Lotofácil, com 5 jogos: a chance de levar algo vai de 44,7% para 47,4%, e a de ganhar em dois bilhetes ao mesmo tempo cai de 8,0% para 5,5%. O RETORNO MÉDIO é idêntico nos dois casos (R$ 4,49) — os efeitos se cancelam. E a chance do prêmio principal não muda: são N em 3.268.760 de qualquer jeito. É preferência de formato, não vantagem." />
                  </span>
                  <span className="block text-xs text-zinc-500">
                    Ganha algo com um pouco mais de frequência, e menos vezes em dois bilhetes de
                    uma vez. O <strong>retorno médio é o mesmo</strong> — e a chance do prêmio
                    principal também.
                  </span>
                </span>
              </label>
            ) : (
              <div />
            )}
            <label className="flex items-start gap-2 text-sm sm:mt-6">
              <input
                type="checkbox"
                checked={antiRateio}
                onChange={(e) => setAntiRateio(e.target.checked)}
                className="mt-0.5 accent-emerald-600"
              />
              <span>
                <span className="text-zinc-800 font-medium inline-flex items-center gap-1.5">
                  Anti-rateio
                  <Help text="Descarta combinações que milhões de pessoas jogam (datas de aniversário, sequências, desenhos no volante, jogos que já foram sena). Não aumenta a chance de ganhar, mas se você ganhar, divide o prêmio com menos gente — efeito real no bolso." />
                </span>
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
            {busy
              ? 'Gerando…'
              : simples
                ? `Gerar ${qtdJogos} jogo(s)`
                : `Gerar aposta de ${dezenas} dezenas`}
          </button>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </Card>

        {cfg.avancada && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              Probabilidades reais
              <Help text="A chance exata de cada prêmio, calculada por matemática (não é estimativa nem 'tendência'). É idêntica para QUALQUER combinação de números — por isso nenhuma estratégia muda estes valores. Só aumentar as dezenas ou a quantidade de bilhetes muda a chance." />
            </span>
          }
          subtitle={
            simples
              ? `${qtdJogos} bilhete(s) de ${cfg.escolher} dezenas`
              : `1 bilhete de ${dezenas} dezenas`
          }
        >
          {(simples ? carteira : odds) ? (
            <div className="space-y-3 text-sm">
              <table className="w-full text-left">
                <tbody>
                  {Object.entries((simples ? carteira : odds).faixas).map(([label, f]) => (
                    <tr key={label} className="border-b border-zinc-100 last:border-0">
                      <td className="py-1.5 text-zinc-600 first-letter:uppercase">{label}</td>
                      <td className="py-1.5 text-right font-semibold tabular-nums">
                        1 em {fmt(f.one_in)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {simples && carteira && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                  <p className="text-xs text-emerald-900">
                    Chance de levar <strong>algum</strong> prêmio
                  </p>
                  <p className="font-bold tabular-nums text-emerald-900">
                    {fmt(carteira.qualquer.pct)}%{' '}
                    <span className="text-xs font-normal">
                      (1 em {fmt(carteira.qualquer.one_in)})
                    </span>
                  </p>
                  {espalhar && qtdJogos > 1 && (
                    <p className="text-[11px] text-emerald-800 mt-0.5">
                      espalhando, essa frequência sobe alguns pontos — o retorno médio não muda
                    </p>
                  )}
                </div>
              )}

              <p className="text-xs text-zinc-600">
                Custo:{' '}
                <strong className="text-emerald-700">
                  {formatMoney(simples ? carteira.custo_estimado : odds.custo_estimado)}
                </strong>
                {!simples && (
                  <>
                    {' '}
                    · equivale a <strong>{fmt(odds.combos_simples)}</strong> apostas simples
                  </>
                )}
              </p>

              {/* A comparação que decide: mesmo dinheiro, formatos diferentes */}
              {!simples && odds && equivalente && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-900 leading-relaxed">
                  <strong>Mesmo dinheiro, do outro jeito:</strong>{' '}
                  {formatMoney(odds.custo_estimado)} compram {fmt(odds.combos_simples)} bilhetes
                  simples separados.
                  <table className="w-full mt-1.5 text-[11px]">
                    <tbody>
                      <tr>
                        <td className="py-0.5">Prêmio principal</td>
                        <td className="py-0.5 text-right font-semibold">idêntico nos dois</td>
                      </tr>
                      <tr>
                        <td className="py-0.5">Levar algo — esta aposta</td>
                        <td className="py-0.5 text-right tabular-nums">{fmt(odds.qualquer.pct)}%</td>
                      </tr>
                      <tr>
                        <td className="py-0.5">Levar algo — bilhetes separados</td>
                        <td className="py-0.5 text-right font-bold tabular-nums">
                          {fmt(equivalente.pct)}%
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              <label className="flex items-center gap-2 text-xs text-zinc-600">
                Preço da aposta simples: R$
                <input
                  value={preco}
                  onChange={(e) => setPreco(e.target.value)}
                  className="w-16 border border-zinc-300 rounded px-1.5 py-1 text-right"
                  inputMode="decimal"
                />
              </label>
              <p className="text-xs text-zinc-500 border-t border-zinc-100 pt-2">
                A única forma real de aumentar a chance é jogar mais combinações (2 jogos = 2× a
                chance) — é assim que os bolões de lotérica “ganham sempre”: volume, não segredo.
              </p>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Carregando…</p>
          )}
        </Card>
        )}
      </div>

      {result && (
        <Card
          title={`Jogos gerados — ${ESTRATEGIAS.find((e) => e.id === result.estrategia)?.nome}`}
          subtitle={result.aviso}
        >
          <label className="flex items-center gap-2 text-sm mb-3">
            <span className="text-zinc-600">Salvar como “jogo do app” no concurso</span>
            <input
              type="number"
              min="1"
              value={concursoSalvar}
              onChange={(e) => setConcursoSalvar(e.target.value)}
              className="w-24 border border-zinc-300 rounded-lg px-2 py-1"
            />
          </label>
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
                <div className="mt-2">
                  {salvos[i] ? (
                    <span className="text-xs text-emerald-700 font-medium">
                      ✓ salvo no concurso {salvos[i]} —{' '}
                      <Link to={`/${code}/meus-jogos`} className="underline">
                        ver em Meus jogos
                      </Link>
                    </span>
                  ) : (
                    <button
                      onClick={() => salvar(i, j)}
                      disabled={!concursoSalvar}
                      className="text-xs px-3 py-1.5 rounded-lg border border-emerald-600 text-emerald-700 font-medium hover:bg-emerald-50 disabled:opacity-50"
                    >
                      Salvar este jogo
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {cfg.avancada && (
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            As estratégias funcionam? Backtest honesto
            <Help text="Teste imparcial: joga cada estratégia contra os últimos 100 sorteios REAIS, usando só o que se sabia antes de cada um (sem trapaça). Se alguma estratégia funcionasse, sua média ficaria acima de 0,6 acerto/jogo. Rode e veja: todas empatam com o puro acaso." />
          </span>
        }
        subtitle="Simula jogar cada estratégia nos últimos 100 concursos, usando só o histórico anterior a cada sorteio — compare com o esperado pelo acaso (0,6 acerto por jogo)"
      >
        {!backtest && (
          <button
            onClick={rodarBacktest}
            disabled={backtestBusy}
            className="px-4 py-2 rounded-lg border border-zinc-300 bg-white text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
          >
            {backtestBusy ? 'Simulando…' : 'Rodar backtest (últimos 100 concursos)'}
          </button>
        )}
        {backtestError && <p className="text-sm text-red-600 mt-2">{backtestError}</p>}
        {backtest && (
          <div className="space-y-3">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200">
                  <th className="py-1.5 font-medium">Estratégia</th>
                  <th className="py-1.5 font-medium text-right">Média de acertos/jogo</th>
                  <th className="py-1.5 font-medium text-right">vs. acaso (0,6)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(backtest.estrategias).map(([nome, r]) => (
                  <tr key={nome} className="border-b border-zinc-100 last:border-0">
                    <td className="py-1.5">{ESTRATEGIAS.find((e) => e.id === nome)?.nome ?? nome}</td>
                    <td className="py-1.5 text-right font-semibold tabular-nums">
                      {r.media_acertos.toFixed(2).replace('.', ',')}
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-zinc-500">
                      {(r.media_acertos - 0.6 >= 0 ? '+' : '') +
                        (r.media_acertos - 0.6).toFixed(2).replace('.', ',')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-zinc-500">
              Concursos {backtest.primeiro_concurso}–{backtest.ultimo_concurso} · todas as
              estratégias flutuam em torno de 0,6 — nenhuma “sabe” algo sobre o próximo sorteio. Se
              alguma parecesse muito acima, seria sorte da amostra, não previsão.
            </p>
          </div>
        )}
      </Card>
      )}
    </div>
  )
}
