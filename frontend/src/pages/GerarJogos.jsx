import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'
import { addBet, exportJogosCSV } from '../lib/bets.js'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import Help from '../components/Help.jsx'
import { formatDate, formatMoney } from '../lib/format.js'
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
const num = (n, d = 2) =>
  n == null ? '—' : n.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })

// Como a prévia do painel foi calculada (texto depois de "sem espalhar seria X% —").
const METODO_PREVIA = {
  enumerado: ' média de lotes medida contando todos os sorteios possíveis',
  combinatorio: ' conta exata a partir das dezenas que os bilhetes dividem entre si',
  simulado: ' estimado por simulação de 60 mil sorteios sobre um lote de exemplo (±0,4 ponto)',
}

// "Em quantos concursos de cada 100": inteiro a partir de 10, uma casa abaixo.
const porCem = (x) => (x >= 9.95 ? String(Math.round(x)) : num(x, 1))

// Quanto o Espalhar muda com a quantidade de jogos digitada. De propósito não
// diz qual opção é "melhor": o dinheiro que volta, em média, é o mesmo nas
// duas — muda só a regularidade. Os números são os do painel (jogos ao acaso).
function QuadroEspalhar({ carteira, qtdJogos, cfg, estrategia }) {
  const sem = 100 * (1 - carteira.qualquer_solto.prob)
  const com = 100 * (1 - carteira.qualquer.prob)
  const diferenca = sem - com
  if (diferenca < 1) {
    return (
      <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 leading-relaxed">
        <strong className="text-zinc-800">
          Espalhar com {qtdJogos} jogos na {cfg.nome}: tanto faz.
        </strong>{' '}
        A cada 100 concursos, você ficaria sem nenhum prêmio em {porCem(sem)} sem Espalhar e em{' '}
        {porCem(com)} com Espalhar — menos de 1 concurso de diferença.
      </div>
    )
  }
  return (
    <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 leading-relaxed">
      <strong>
        Espalhar com {qtdJogos} jogos na {cfg.nome}: faz {diferenca < 3 ? 'pouca ' : ''}diferença.
      </strong>{' '}
      A cada 100 concursos, você ficaria sem nenhum prêmio em <strong>{porCem(sem)}</strong> sem
      Espalhar e em <strong>{porCem(com)}</strong> com Espalhar. Em troca, com o Espalhar ficam mais
      raros os concursos com muitos prêmios juntos. O dinheiro que volta, em média, é o mesmo:
      ligue se prefere receber algo com mais frequência.
      {estrategia === 'atrasados' && (
        <span className="block mt-1 text-emerald-800">
          Estes números supõem jogos ao acaso. Com Atrasados, os jogos repetem as mesmas dezenas
          atrasadas e, sem Espalhar, ficam sem prêmio mais vezes — depois de gerar, o app mostra a
          conta dos seus jogos.
        </span>
      )}
    </div>
  )
}

const METODO_LOTE = {
  exato: ' (conta exata)',
  combinatorio: ' (conta exata)',
  simulado: ' (simulação de 60 mil sorteios, margem de ±0,4 ponto)',
}

// A chance de levar algum prêmio com os jogos que saíram de verdade — que
// depende de quanto eles repetem dezenas entre si, e por isso da estratégia.
function ChanceDoLote({ carteira, jogos, referencia }) {
  const q = carteira.qualquer
  const abaixo = referencia != null ? 100 * (referencia - q.prob) : 0
  return (
    <div className="text-xs rounded-lg border px-3 py-2 mb-3 leading-relaxed bg-emerald-50 border-emerald-200 text-emerald-900">
      Com <strong>estes {jogos} jogos</strong>, a chance de levar algum prêmio é de{' '}
      <strong>{fmt(q.pct)}%</strong>: sem nenhum prêmio em ~{porCem(100 * (1 - q.prob))} de cada
      100 concursos{METODO_LOTE[carteira.metodo] ?? ''}.
      {abaixo >= 1.5 && (
        <>
          {' '}
          Isso fica <strong>{num(abaixo, 1)} ponto(s) abaixo</strong> de jogos ao acaso, porque os
          seus jogos repetem mais dezenas entre si. O retorno médio não muda.
        </>
      )}
    </div>
  )
}

// Teste no passado: janelas e lotes que a tela oferece. 200 vem marcado por
// ser a janela em que a sorte pesa menos — o próprio resultado mostra quanto.
const JANELAS_TESTE = [50, 100, 200]
const JOGOS_TESTE = [1, 2, 3, 4, 5]

const ROTULO_POSICAO = { normal: 'normal', acima: 'acima do normal', abaixo: 'abaixo do normal' }
const COR_POSICAO = {
  normal: 'bg-zinc-100 text-zinc-600',
  acima: 'bg-emerald-100 text-emerald-800',
  abaixo: 'bg-amber-100 text-amber-800',
}

// Onde um resultado cai na faixa que a sorte, sozinha, produz.
const posicao = (valor, min, max) => (valor < min ? 'abaixo' : valor > max ? 'acima' : 'normal')

// "de 0 a 2", ou só "0" quando a faixa é um número só
const deAte = (min, max) => (min === max ? `${min}` : `de ${min} a ${max}`)

const jogosTexto = (n) => `${n} jogo${n > 1 ? 's' : ''}`

// "11, 12 e 13"
const lista = (itens) =>
  itens.length > 1 ? `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}` : `${itens[0] ?? ''}`

const nomeEstrategia = (id) => ESTRATEGIAS.find((e) => e.id === id)?.nome ?? id

function Posicao({ valor, min, max }) {
  const p = posicao(valor, min, max)
  return (
    <span className={`ml-1.5 inline-block text-[10px] font-medium px-1.5 py-0.5 rounded ${COR_POSICAO[p]}`}>
      {ROTULO_POSICAO[p]}
    </span>
  )
}

function Escolha({ rotulo, opcoes, valor, onChange }) {
  return (
    <div className="text-sm">
      <span className="block text-zinc-600 mb-1">{rotulo}</span>
      <div
        role="group"
        aria-label={rotulo}
        className="inline-flex rounded-lg border border-zinc-300 overflow-hidden"
      >
        {opcoes.map((o) => (
          <button
            key={o}
            type="button"
            aria-pressed={valor === o}
            onClick={() => onChange(o)}
            className={`px-3 py-1.5 tabular-nums border-l border-zinc-300 first:border-l-0 ${
              valor === o
                ? 'bg-emerald-600 text-white font-semibold'
                : 'bg-white text-zinc-700 hover:bg-zinc-50'
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  )
}

// "56× 11 pts · 9× 12 pts" na Lotofácil; "1 quadra" na Mega. Só o que saiu.
// Cada faixa fica inteira na linha; a quebra, se precisar, é entre elas.
function PremiosDoTeste({ premios, cfg }) {
  const saiu = cfg.premios.filter((p) => (premios[p.ac] ?? 0) > 0).reverse()
  if (!saiu.length) return 'nenhum'
  return saiu.map((p, i) => {
    const q = premios[p.ac]
    return (
      <span key={p.ac} className="whitespace-nowrap">
        {i > 0 && ' · '}
        {/^\d/.test(p.label) ? `${q}× ${p.ac} pts` : `${q} ${p.label.toLowerCase()}${q > 1 ? 's' : ''}`}
      </span>
    )
  })
}

// Quanto a sorte, sozinha, mexe no resultado em cada janela — a resposta a
// "50, 100 ou 200?".
function QualJanela({ resultado, premioRaro, cfg }) {
  const { acaso, concursos_simulados: n, jogos_por_concurso: jogos } = resultado
  const j50 = acaso.janelas.find((j) => j.concursos === 50)
  const j200 = acaso.janelas.find((j) => j.concursos === 200)
  const pct = (x, total) => `${num((100 * x) / total, 0)}%`
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-xs text-zinc-600 leading-relaxed">
      <p className="font-medium text-zinc-800">Por que 200 concursos, e não 50 ou 100?</p>
      <table className="w-full mt-1.5 tabular-nums">
        <thead>
          <tr className="text-zinc-500">
            <th className="py-0.5 font-medium text-left">Concursos</th>
            <th className="py-0.5 font-medium text-right">
              {premioRaro ? 'Acertos por jogo, só por sorte' : 'Ganhar algo, só por sorte'}
            </th>
          </tr>
        </thead>
        <tbody>
          {acaso.janelas.map((j) => (
            <tr key={j.concursos} className={j.concursos === n ? 'font-semibold text-zinc-800' : ''}>
              <td className="py-0.5">{j.concursos}</td>
              <td className="py-0.5 text-right">
                {premioRaro
                  ? `de ${num(j.media_min)} a ${num(j.media_max)}`
                  : `de ${j.min} a ${j.max} vezes (${pct(j.min, j.concursos)}–${pct(j.max, j.concursos)})`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {premioRaro ? (
        <p className="mt-1.5">
          Na {cfg.nome}, nenhuma das três janelas mede prêmio: com {jogosTexto(jogos)} por concurso, o
          normal em 200 concursos é {deAte(j200.min, j200.max)}. O que dá para comparar é a média de
          acertos, e com 50 concursos ela varia de {num(j50.media_min)} a {num(j50.media_max)} só
          por sorte. <strong>Use 200</strong>: a faixa fica com metade da largura da de 50. Mesmo
          assim, diferença pequena entre estratégias continua sendo sorte.
        </p>
      ) : (
        <p className="mt-1.5">
          Quanto menos concursos, mais larga a faixa da sorte. Com 50, uma estratégia pode ganhar
          algo em {pct(j50.max, 50)} dos concursos e outra em {pct(j50.min, 50)} sem nenhuma ser
          melhor: o teste vira loteria. <strong>Use 200</strong>: é a janela mais confiável das
          três. Mas nem ela aponta a estratégia “certa” — a diferença real entre elas é zero ou
          pequena demais para aparecer. Os últimos 50 servem só para ver o que aconteceu
          recentemente.
        </p>
      )}
    </div>
  )
}

function TesteNoPassado({ cfg }) {
  const [concursos, setConcursos] = useState(200)
  const [jogos, setJogos] = useState(3)
  const [espalhar, setEspalhar] = useState(true)
  const [resultado, setResultado] = useState(null)
  const [busy, setBusy] = useState(false)
  const [erro, setErro] = useState(null)
  const pedido = useRef(0)

  // Trocou a pergunta: o resultado na tela deixa de responder a ela, e uma
  // resposta ainda a caminho (da pergunta anterior) é descartada.
  useEffect(() => {
    pedido.current += 1
    setResultado(null)
    setErro(null)
    setBusy(false)
  }, [concursos, jogos, espalhar])

  async function rodar() {
    const meu = ++pedido.current
    setBusy(true)
    setErro(null)
    try {
      const r = await apiPost(
        `/backtest?ultimos=${concursos}&jogos=${jogos}&espalhar=${espalhar && jogos > 1}`,
      )
      if (meu === pedido.current) setResultado(r)
    } catch (e) {
      if (meu === pedido.current) setErro(e.message)
    } finally {
      if (meu === pedido.current) setBusy(false)
    }
  }

  const r = resultado
  const a = r?.acaso
  const n = r?.concursos_simulados
  const linhas = r ? Object.entries(r.estrategias) : []
  // Na Mega, prêmio com até 5 jogos é raro demais: o normal em 200 concursos
  // é 0 a 2. Aí a comparação possível é pela média de acertos.
  const premioRaro = a ? a.max <= 2 : false
  const fora = a
    ? linhas.filter(([, e]) =>
        premioRaro
          ? posicao(e.media_acertos, a.media_min, a.media_max) !== 'normal'
          : posicao(e.concursos_com_premio, a.min, a.max) !== 'normal',
      )
    : []
  const temRetorno = linhas.some(([, e]) => e.retorno_fixo != null)
  const fixos = cfg.premios.filter((p) => p.label.includes('fixo')).map((p) => p.ac).sort((x, y) => x - y)
  const variaveis = cfg.premios.filter((p) => !p.label.includes('fixo')).map((p) => p.ac).sort((x, y) => x - y)
  const menorPremio = r && cfg.premios.find((p) => p.ac === r.faixa_minima)?.label.split(' · ')[0].toLowerCase()
  const nomesFora = lista(fora.map(([id]) => nomeEstrategia(id)))

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          Teste no passado: qual estratégia teria se saído melhor?
          <Help text="Para cada concurso passado, o app gera os jogos de cada estratégia usando só os sorteios anteriores — sem olhar o resultado — e confere com o que saiu de verdade. A faixa normal mostra quanto o resultado varia só por sorte: dentro dela, a diferença entre as estratégias não quer dizer nada." />
        </span>
      }
      subtitle="Simula o seu jeito de jogar nos últimos concursos e compara com o que a sorte, sozinha, produz."
    >
      <div className="flex flex-wrap items-end gap-4">
        <Escolha
          rotulo="Últimos concursos"
          opcoes={JANELAS_TESTE}
          valor={concursos}
          onChange={setConcursos}
        />
        <Escolha rotulo="Jogos por concurso" opcoes={JOGOS_TESTE} valor={jogos} onChange={setJogos} />
        {jogos > 1 && (
          <label className="flex items-center gap-2 text-sm pb-1.5">
            <input
              type="checkbox"
              checked={espalhar}
              onChange={(e) => setEspalhar(e.target.checked)}
              className="accent-emerald-600"
            />
            Espalhar os jogos
          </label>
        )}
        <button
          onClick={rodar}
          disabled={busy}
          className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
        >
          {busy ? 'Simulando…' : 'Rodar teste'}
        </button>
      </div>
      {busy && (
        <p className="text-xs text-zinc-500 mt-2">
          {concursos} concursos × {jogosTexto(jogos)} × 4 estratégias. A primeira vez pode levar uns 20
          segundos; depois, trocar para menos concursos ou menos jogos sai na hora.
        </p>
      )}
      {!r && !busy && !erro && (
        <p className="text-xs text-zinc-500 mt-2">
          Prefira 200 concursos: com menos, a sorte pesa mais — o resultado mostra quanto.
        </p>
      )}
      {erro && <p className="text-sm text-red-600 mt-2">{erro}</p>}
      {r && (
        <div className="space-y-3 mt-4">
          <div className="rounded-lg border px-3 py-2 text-xs leading-relaxed bg-zinc-50 border-zinc-200 text-zinc-700">
            {premioRaro ? (
              <p>
                <strong>Na {cfg.nome}, prêmio é raro demais para este teste:</strong> com{' '}
                {jogosTexto(r.jogos_por_concurso)} por concurso, o acaso dá prêmio ({menorPremio} ou
                mais) em 1 de cada {fmt(Math.round(1 / a.chance_por_concurso))} concursos. Em {n}{' '}
                concursos, o normal é {deAte(a.min, a.max)}: pouco demais para separar estratégias.
                Compare pela <strong>média de acertos por jogo</strong>, que só por sorte fica entre{' '}
                <strong>
                  {num(a.media_min)} e {num(a.media_max)}
                </strong>
                .
              </p>
            ) : (
              <p>
                <strong>Faixa normal da sorte:</strong> com {jogosTexto(r.jogos_por_concurso)}
                {r.espalhar ? ' espalhados' : ''} por concurso, o acaso dá algum prêmio em{' '}
                {porCem(100 * a.chance_por_concurso)} de cada 100 concursos. Em {n} concursos, o
                normal é ganhar algo de{' '}
                <strong>
                  {a.min} a {a.max} vezes
                </strong>
                , com qualquer estratégia.
              </p>
            )}
            <p className="mt-1">
              {fora.length === 0 ? (
                <>
                  <strong>Todas ficaram dentro da faixa normal.</strong> A diferença entre elas é
                  sorte: nenhuma estratégia está melhor que as outras.
                </>
              ) : (
                <>
                  <strong>
                    {nomesFora} {fora.length > 1 ? 'ficaram' : 'ficou'} fora da faixa normal.
                  </strong>{' '}
                  Com 4 estratégias disputando, alguma cair fora por sorte acontece de vez em
                  quando — não quer dizer que funcione (nem que seja ruim).
                </>
              )}
            </p>
          </div>

          {premioRaro ? (
            // Prêmio quase nunca sai: o que compara é a média de acertos, e
            // ela vem logo depois do nome (cabe no celular sem rolar).
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200 align-bottom">
                  <th className="py-1.5 pr-3 font-medium">Estratégia</th>
                  <th className="py-1.5 font-medium text-right">
                    Acertos por jogo
                    <span className="block font-normal">
                      normal: {num(a.media_min)} a {num(a.media_max)}
                    </span>
                  </th>
                  <th className="py-1.5 pl-3 font-medium text-right">Prêmios</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map(([id, e]) => (
                  <tr key={id} className="border-b border-zinc-100 last:border-0">
                    <td className="py-1.5 pr-3">{nomeEstrategia(id)}</td>
                    <td className="py-1.5 text-right tabular-nums whitespace-nowrap">
                      <strong>{num(e.media_acertos)}</strong>
                      <Posicao valor={e.media_acertos} min={a.media_min} max={a.media_max} />
                    </td>
                    <td className="py-1.5 pl-3 text-right text-xs text-zinc-600">
                      <PremiosDoTeste premios={e.premios} cfg={cfg} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] text-sm text-left">
                <thead>
                  <tr className="text-xs text-zinc-500 border-b border-zinc-200 align-bottom">
                    <th className="py-1.5 pr-3 font-medium">Estratégia</th>
                    <th className="py-1.5 font-medium text-right">
                      Concursos com prêmio
                      <span className="block font-normal">
                        normal: {a.min} a {a.max}
                      </span>
                    </th>
                    <th className="py-1.5 pl-3 font-medium">Jogos premiados</th>
                    {temRetorno && <th className="py-1.5 pl-3 font-medium text-right">Voltou</th>}
                    <th className="py-1.5 pl-3 font-medium text-right whitespace-nowrap">
                      Acertos por jogo
                      <span className="block font-normal">
                        normal: {num(a.media_min)} a {num(a.media_max)}
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {linhas.map(([id, e]) => (
                    <tr key={id} className="border-b border-zinc-100 last:border-0">
                      <td className="py-1.5 pr-3">{nomeEstrategia(id)}</td>
                      <td className="py-1.5 text-right tabular-nums whitespace-nowrap">
                        <strong>{e.concursos_com_premio}</strong> de {n}
                        <Posicao valor={e.concursos_com_premio} min={a.min} max={a.max} />
                      </td>
                      <td className="py-1.5 pl-3 text-xs text-zinc-600">
                        <PremiosDoTeste premios={e.premios} cfg={cfg} />
                      </td>
                      {temRetorno && (
                        <td className="py-1.5 pl-3 text-right tabular-nums">
                          {formatMoney(e.retorno_fixo)}
                        </td>
                      )}
                      <td className="py-1.5 pl-3 text-right tabular-nums">{num(e.media_acertos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="text-xs text-zinc-500">
            Concursos {r.primeiro_concurso} a {r.ultimo_concurso} ({formatDate(r.primeira_data)} a{' '}
            {formatDate(r.ultima_data)}). Cada estratégia custaria{' '}
            <strong>{formatMoney(r.gasto)}</strong> ({n} concursos × {jogosTexto(r.jogos_por_concurso)}{' '}
            × {formatMoney(cfg.preco)}).{' '}
            {temRetorno
              ? `“Voltou” soma só os prêmios de valor fixo (${lista(fixos)} acertos); ${lista(variaveis)} acertos mudam a cada concurso e aparecem só na contagem de jogos premiados.`
              : `Os prêmios da ${cfg.nome} mudam a cada concurso, por isso não há coluna de quanto voltou.`}
          </p>

          <QualJanela resultado={r} premioRaro={premioRaro} cfg={cfg} />
        </div>
      )}
    </Card>
  )
}

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
  //
  // Buscamos SEMPRE com espalhar=true porque a resposta traz os dois valores
  // de uma vez: `qualquer` (espalhado) e `qualquer_solto` (bilhetes soltos).
  // Assim o painel e a explicação do checkbox leem da MESMA fonte — antes a
  // explicação trazia números fixos, medidos à parte, que contradiziam o
  // painel logo abaixo (dizia 44,7% onde o painel mostrava 42,86%), e citava
  // números da Lotofácil mesmo na tela da Mega.
  const espalharAtivo = simples && espalhar && qtdJogos > 1
  useEffect(() => {
    apiGet(`/odds/carteira?jogos=${qtdJogos}&espalhar=true`)
      .then(setCarteira)
      .catch(() => setCarteira(null))
  }, [qtdJogos])

  // O que o painel mostra depende do checkbox; os dois números saem da mesma
  // resposta, então painel e explicação são sempre coerentes entre si.
  const chanceAlgo = carteira && (espalharAtivo ? carteira.qualquer : carteira.qualquer_solto)
  // Onde os bilhetes já quase não se tocam (o caso da Mega: 6 dezenas em 60),
  // espalhar não tem o que redistribuir e os dois valores coincidem. Dizer
  // "vai de 0,22% para 0,22%" é verdade, mas lê como defeito — então o texto
  // reconhece o empate em vez de fingir que houve ganho.
  const mesmaChance =
    carteira && fmt(carteira.qualquer_solto.pct) === fmt(carteira.qualquer.pct)
  const ajudaEspalhar = !carteira
    ? 'Faz os seus bilhetes serem diferentes entre si, em vez de quase iguais. O resultado fica ' +
      'mais regular: menos concursos sem nenhum prêmio e menos concursos com muitos prêmios ' +
      'juntos. O retorno médio é idêntico nos dois casos, e a chance do prêmio principal não ' +
      'muda. É preferência de formato, não vantagem.'
    : mesmaChance
      ? `Faz os seus bilhetes serem diferentes entre si, em vez de quase iguais. Na ${cfg.nome} ` +
        `isso quase não muda nada: com ${qtdJogos} bilhetes de ${cfg.escolher} dezenas em ` +
        `${cfg.total}, eles já saem praticamente sem se tocar, então a chance de levar algum ` +
        `prêmio fica em ${fmt(carteira.qualquer.pct)}% dos dois jeitos` +
        `${carteira.metodo === 'exato' ? ' — e já é o máximo possível' : ''}. ` +
        `Espalhar rende de verdade onde os bilhetes são obrigados a se sobrepor, ` +
        `como na Lotofácil (15 dezenas em 25). O retorno médio e a chance do prêmio principal ` +
        `não mudam em nenhum caso.`
      : `Faz os seus bilhetes serem diferentes entre si, em vez de quase iguais. Com ${qtdJogos} ` +
        `bilhetes na ${cfg.nome}, a chance de levar algum prêmio vai de ` +
        `${fmt(carteira.qualquer_solto.pct)}% (bilhetes soltos) para ${fmt(carteira.qualquer.pct)}% — ` +
        `são os mesmos números do painel ao lado. Em compensação, ficam mais raros os concursos ` +
        `com muitos prêmios juntos: o RETORNO MÉDIO é idêntico nos dois casos, porque um efeito ` +
        `compensa o outro. E a chance do prêmio principal não muda: são ${qtdJogos} bilhetes ` +
        `entre as mesmas combinações possíveis de qualquer jeito. É preferência de formato, ` +
        `não vantagem.`

  // O Espalhar só existe entre 2+ bilhetes simples do mesmo pedido; fora
  // disso (1 jogo, aposta múltipla) grava null = "não se aplica", para não
  // registrar "desligado" onde a opção nem tinha efeito.
  function espalharDoLote() {
    return result.jogos.length > 1 && result.dezenas === cfg.escolher ? Boolean(result.espalhar) : null
  }

  function salvar(i, jogo) {
    if (!concursoSalvar) return
    addBet({
      loteria: code,
      concurso: concursoSalvar,
      origem: 'app',
      estrategia: result.estrategia,
      espalhar: espalharDoLote(),
      dezenas: jogo.dezenas,
    })
    setSalvos((s) => ({ ...s, [i]: concursoSalvar }))
  }

  // Salva todo mundo que ainda não foi salvo, um addBet() por jogo (é o mesmo
  // caminho do botão individual — só evita clicar jogo por jogo num lote grande).
  function salvarTodos() {
    if (!concursoSalvar || !result) return
    const novos = { ...salvos }
    const espalhar = espalharDoLote()
    for (const [i, jogo] of result.jogos.entries()) {
      if (novos[i]) continue
      addBet({
        loteria: code,
        concurso: concursoSalvar,
        origem: 'app',
        estrategia: result.estrategia,
        espalhar,
        dezenas: jogo.dezenas,
      })
      novos[i] = concursoSalvar
    }
    setSalvos(novos)
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
      // A prévia do painel supõe jogos ao acaso; guardada aqui para comparar
      // com a chance dos jogos que saíram de verdade.
      const referencia = carteira?.jogos === qtdJogos && chanceAlgo ? chanceAlgo.prob : null
      setResult({ ...r, referencia })
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
                  <Help text="Quantos bilhetes simples separados gerar (1 a 200). Cada bilhete a mais aumenta a sua chance de verdade, na proporção do que custa: 2 jogos = 2x a chance do prêmio principal. O teto de 200 (~2s de geração) fica bem longe do limite de 60s da função serverless — acima disso o tempo cresce quadrático (cada bilhete novo é comparado com todos os anteriores no espalhamento)." />
                </span>
                <input
                  type="number"
                  min="1"
                  max="200"
                  value={qtdJogos}
                  onChange={(e) => setQtdJogos(Math.min(200, Math.max(1, Number(e.target.value))))}
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
                    <Help text={ajudaEspalhar} />
                  </span>
                  <span className="block text-xs text-zinc-500">
                    Menos concursos sem nenhum prêmio e menos com muitos prêmios juntos. O{' '}
                    <strong>retorno médio é o mesmo</strong> — e a chance do prêmio principal
                    também.
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

          {simples && qtdJogos > 1 && carteira?.jogos === qtdJogos && (
            <QuadroEspalhar carteira={carteira} qtdJogos={qtdJogos} cfg={cfg} estrategia={estrategia} />
          )}

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
                    {espalharAtivo ? ' (espalhando)' : ''}
                  </p>
                  <p className="font-bold tabular-nums text-emerald-900">
                    {fmt(chanceAlgo.pct)}%{' '}
                    <span className="text-xs font-normal">
                      (1 em {fmt(chanceAlgo.one_in)})
                    </span>
                  </p>
                  {espalharAtivo ? (
                    <p className="text-[11px] text-emerald-800 mt-0.5 leading-relaxed">
                      {carteira.metodo === 'exato' ? (
                        <>
                          este é o <strong>teto</strong>: espalhados, os seus bilhetes não podem
                          premiar dois no mesmo sorteio, então a chance é a de um bilhete vezes{' '}
                          {qtdJogos}, sem perda nenhuma
                        </>
                      ) : (
                        <>
                          sem espalhar seria <strong>{fmt(carteira.qualquer_solto.pct)}%</strong> —
                          {METODO_PREVIA[carteira.metodo] ?? ''}
                        </>
                      )}
                      . O retorno médio é o mesmo nos dois casos.
                    </p>
                  ) : (
                    qtdJogos > 1 && (
                      <p className="text-[11px] text-emerald-800 mt-0.5">
                        marcando “espalhar os jogos” essa frequência sobe — o retorno médio não muda
                      </p>
                    )
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
          {result.carteira?.lote && result.jogos.length > 1 && (
            <ChanceDoLote
              carteira={result.carteira}
              jogos={result.jogos.length}
              referencia={result.referencia}
            />
          )}
          {result.sobreposicao && (
            <div
              className={`text-xs rounded-lg border px-3 py-2 mb-3 leading-relaxed ${
                result.sobreposicao.sem_custo
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-zinc-50 border-zinc-200 text-zinc-600'
              }`}
            >
              Seus bilhetes repetem no máximo{' '}
              <strong>{result.sobreposicao.maxima} dezenas</strong> entre si (média{' '}
              {num(result.sobreposicao.media, 1)}).{' '}
              {result.sobreposicao.sem_custo ? (
                <>
                  Até <strong>{result.sobreposicao.limiar}</strong> não custa nada: dois bilhetes só
                  podem premiar no mesmo sorteio a partir de {result.sobreposicao.limiar + 1}{' '}
                  dezenas em comum, então a sua chance de levar algo já está no{' '}
                  <strong>máximo possível</strong> — a de um bilhete, multiplicada por{' '}
                  {result.jogos.length}.
                </>
              ) : (
                <>
                  Acima de <strong>{result.sobreposicao.limiar}</strong> cada dezena repetida troca
                  “levar algo mais vezes” por “levar em dois bilhetes de uma vez”. O retorno médio
                  não muda em nenhum dos casos — e é só isto que a escolha de dezenas pode mexer num
                  conjunto de bilhetes: a estratégia em si não altera nada.
                </>
              )}
              {result.sobreposicao.piso > 0 && (
                <>
                  {' '}
                  O mínimo possível na {cfg.nome} é <strong>{result.sobreposicao.piso}</strong>,
                  porque {cfg.escolher}+{cfg.escolher} dezenas não cabem em {cfg.total} sem encostar
                  {!result.sobreposicao.otimo_possivel && (
                    <> — com {result.jogos.length} bilhetes a zona gratuita é inalcançável</>
                  )}
                  .
                </>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-zinc-600">Salvar como “jogo do app” no concurso</span>
              <input
                type="number"
                min="1"
                value={concursoSalvar}
                onChange={(e) => setConcursoSalvar(e.target.value)}
                className="w-24 border border-zinc-300 rounded-lg px-2 py-1"
              />
            </label>
            <button
              onClick={salvarTodos}
              disabled={!concursoSalvar || result.jogos.every((_, i) => salvos[i])}
              className="text-xs px-3 py-1.5 rounded-lg border border-emerald-600 text-emerald-700 font-medium hover:bg-emerald-50 disabled:opacity-50"
            >
              Salvar todos os jogos
            </button>
            <button
              onClick={() => exportJogosCSV(result.jogos, code)}
              className="text-xs px-3 py-1.5 rounded-lg border border-zinc-300 text-zinc-700 font-medium hover:bg-zinc-50"
            >
              Exportar CSV
            </button>
          </div>
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

      {cfg.avancada && <TesteNoPassado cfg={cfg} />}
    </div>
  )
}
