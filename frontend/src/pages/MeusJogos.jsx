import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'
import { addBets, exportBets, importBets, loadBets, removeBet, removeBets, syncBets } from '../lib/bets.js'
import { clearSession, extrairToken, getSession, logout, requestLink, verifyToken } from '../lib/auth.js'
import { useLottery } from '../lib/LotteryContext.jsx'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import Volante from '../components/Volante.jsx'
import { formatDate } from '../lib/format.js'
import { MIN_CONCURSOS, desempenhoPorEstrategia } from '../lib/desempenho.js'
import { EVENTO_SORTEIOS } from '../lib/sincronizar.js'

// Cor por faixa premiada. As chaves vêm do backend (Mega: sena/quina/quadra;
// Lotofácil: "15 acertos" … "11 acertos").
const FAIXA_STYLE = {
  sena: 'bg-emerald-600 text-white',
  quina: 'bg-amber-500 text-white',
  quadra: 'bg-blue-600 text-white',
  '15 acertos': 'bg-purple-600 text-white',
  '14 acertos': 'bg-purple-500 text-white',
  '13 acertos': 'bg-amber-500 text-white',
  '12 acertos': 'bg-blue-600 text-white',
  '11 acertos': 'bg-blue-500 text-white',
}

const ORIGEM_LABEL = { manual: 'Meu jogo (manual)', app: 'Jogo do app' }

const reais = (v) => `R$ ${num(v, 2)}`

// Combinações: quantas apostas simples cabem numa aposta de k dezenas.
function comb(n, k) {
  if (k < 0 || k > n) return 0
  let r = 1
  for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i
  return Math.round(r)
}

// Lê jogos colados como texto, um por linha. Aceita qualquer separador
// ("01 02 03", "1,2,3", "01-02-03") e um rótulo no começo ("Jogo 1: …",
// "A) …"), que é o formato do comprovante de bolão da lotérica.
function lerJogos(texto, cfg) {
  const jogos = []
  const erros = []
  const linhas = texto.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  linhas.forEach((linha, i) => {
    const semRotulo = linha.replace(/^\s*[a-zA-ZÀ-ú]+\.?\s*\d*\s*[:)\-–]\s*/, '')
    const dz = (semRotulo.match(/\d+/g) || []).map(Number)
    const n = i + 1
    if (dz.length < cfg.escolher || dz.length > cfg.maxEscolher) {
      erros.push(`linha ${n}: ${dz.length} dezena(s) — a ${cfg.nome} aceita de ${cfg.escolher} a ${cfg.maxEscolher}`)
    } else if (new Set(dz).size !== dz.length) {
      erros.push(`linha ${n}: dezena repetida`)
    } else if (dz.some((d) => d < cfg.min || d > cfg.max)) {
      erros.push(`linha ${n}: dezena fora de ${cfg.min} a ${cfg.max}`)
    } else {
      jogos.push([...dz].sort((a, b) => a - b))
    }
  })
  return { jogos, erros }
}

// "1 sena + 6 quinas" — os prêmios que uma aposta (ou um bolão inteiro) leva.
function premiosTexto(premios) {
  return premios
    .map((p) => {
      // Lotofácil: "3× 13 acertos"; Mega: "6 quinas"
      if (/^\d/.test(p.faixa)) return `${p.quantidade}× ${p.faixa}`
      return `${p.quantidade} ${p.quantidade > 1 ? `${p.faixa}s` : p.faixa}`
    })
    .join(' + ')
}

// Jogos de bolão de um concurso, agrupados pelo nome, na ordem em que entraram.
function boloesDe(grupo) {
  const por = new Map()
  for (const b of [...grupo].sort((x, y) => String(x.criado_em).localeCompare(String(y.criado_em)))) {
    if (b.origem !== 'bolao') continue
    if (!por.has(b.bolao)) por.set(b.bolao, [])
    por.get(b.bolao).push(b)
  }
  return [...por.entries()]
}

// Soma os prêmios de vários jogos por faixa (maior faixa primeiro).
function somarPremios(checks) {
  const por = new Map()
  for (const c of checks) {
    for (const p of c?.premios ?? []) {
      const atual = por.get(p.acertos) ?? { ...p, quantidade: 0, valor: p.valor != null ? 0 : undefined }
      atual.quantidade += p.quantidade
      if (p.valor != null) atual.valor += p.valor
      por.set(p.acertos, atual)
    }
  }
  return [...por.values()].sort((a, b) => b.acertos - a.acertos)
}

const num = (n, d = 2) =>
  n == null ? '—' : n.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })

// Cor do veredito: verde para acima do esperado, âmbar para abaixo, neutro
// para o que o acaso produz na maioria das vezes. "Típico" é deliberadamente
// cinza — não é bom nem ruim, é o resultado normal.
const NIVEL_STYLE = {
  acima: 'bg-emerald-50 border-emerald-200 text-emerald-900',
  tipico: 'bg-zinc-50 border-zinc-200 text-zinc-600',
  abaixo: 'bg-amber-50 border-amber-200 text-amber-900',
}

/* Situa os acertos do jogo na distribuição do acaso. Sem isto não há como
   julgar o próprio resultado: 9 acertos na Lotofácil parece muito e é
   exatamente a média de QUALQUER jogo de 15 dezenas. */
function Avaliacao({ av, faixa }) {
  if (!av) return null
  const [lo, hi] = av.faixa_tipica
  const faltaram = av.menor_faixa_premiada != null ? av.menor_faixa_premiada - av.acertos : null
  return (
    <p
      className={`text-[11px] border rounded px-2 py-1 mt-2 leading-relaxed ${
        NIVEL_STYLE[av.nivel] ?? NIVEL_STYLE.tipico
      }`}
    >
      <strong className="first-letter:uppercase">{av.veredito}</strong> — um jogo de {av.dezenas}{' '}
      dezenas faz {num(av.esperado, 1)} acertos em média (o normal é cair entre {num(lo, 1)} e{' '}
      {num(hi, 1)}). Contra este resultado, {num(av.pct_pior, 0)}% de todos os jogos possíveis
      teriam acertado menos e {num(av.pct_melhor, 0)}% teriam acertado mais.
      {!faixa && faltaram > 0 && (
        <>
          {' '}
          Faltaram <strong>{faltaram}</strong> para a faixa mínima ({av.menor_faixa_premiada}{' '}
          acertos), que sai em {num(av.premiado.pct, 1)}% dos jogos — 1 em {av.premiado.one_in}.
        </>
      )}
    </p>
  )
}

const VEREDITO_STYLE = {
  ...NIVEL_STYLE,
  insuficiente: 'bg-white border-dashed border-zinc-300 text-zinc-400',
}

// Sinal decidido DEPOIS de arredondar: −0,001 não pode virar "−0,00".
const sinal = (n, d = 2) => {
  const r = Number(n.toFixed(d))
  return (r > 0 ? '+' : r < 0 ? '−' : '') + num(Math.abs(r), d)
}

function Veredito({ linha }) {
  return (
    <span
      className={`text-[11px] border rounded px-1.5 py-0.5 whitespace-nowrap ${
        VEREDITO_STYLE[linha.nivel]
      }`}
    >
      {linha.veredito}
    </span>
  )
}

const premiosTxt = (l) => num(l.premiadosEsperados, l.premiadosEsperados < 1 ? 2 : 1)

/* Diferença para o acaso com o intervalo, numa escala comum a todas as
   linhas: o traço vertical é o zero (o que qualquer jogo faz em média). Se a
   barra cruza o traço, a estratégia não se distingue do acaso. */
function BarraIC({ linha, escala }) {
  const pos = (v) => `${50 + (Math.max(-escala, Math.min(escala, v)) / escala) * 50}%`
  const [lo, hi] = linha.ic
  return (
    <div className="relative h-4 w-28 sm:w-36" aria-hidden="true">
      <div className="absolute inset-y-0 left-1/2 w-px bg-zinc-400" />
      <div
        className={`absolute top-1/2 h-1 -translate-y-1/2 rounded-full ${
          linha.nivel === 'insuficiente' ? 'bg-zinc-200' : 'bg-zinc-300'
        }`}
        style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }}
      />
      <div
        className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-zinc-700"
        style={{ left: pos(linha.diferenca) }}
      />
    </div>
  )
}

// Esperado com poucas casas: "0,9" diz mais que "0,94", e o que é quase
// impossível vira "~0" em vez de uma fila de zeros.
const espTxt = (v) => (v < 0.05 ? '~0' : num(v, v < 10 ? 1 : 0))

/* Quantos jogos de cada estratégia fizeram 0, 1, 2… acertos. É o que a média
   esconde: muitos jogos de 1 acerto e um jogo de 3 podem dar a mesma média,
   mas só o segundo chega perto do prêmio. Embaixo de cada contagem, quantos
   jogos o acaso daria — sem isso, "1 jogo com 3 acertos" não diz se foi bom. */
function DistribuicaoAcertos({ linhas, cfg }) {
  const desde = cfg.acertosDesde ?? 0
  const colunas = []
  for (let h = desde; h <= cfg.sorteadas; h++) colunas.push(h)
  // A primeira coluna junta tudo até `desde` (na Lotofácil, "≤7").
  const valor = (arr, h) => (h === desde ? arr.slice(0, h + 1).reduce((s, v) => s + v, 0) : arr[h])
  const premiadas = new Set(cfg.premios.map((p) => p.ac))
  return (
    <Card
      title={`Quantos números cada jogo acertou — ${cfg.nome}`}
      subtitle="Nº de jogos de cada estratégia por quantidade de acertos · embaixo, em cinza, quantos o acaso daria para a mesma quantidade de jogos"
    >
      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-xs sm:text-sm">
          <thead>
            <tr className="text-zinc-500 border-b border-zinc-200">
              <th className="py-1.5 px-1 font-medium text-left sticky left-0 bg-white">
                Acertos →
              </th>
              {colunas.map((h) => (
                <th
                  key={h}
                  className={`py-1.5 px-1 font-semibold text-center tabular-nums ${
                    premiadas.has(h) ? `${cfg.tintClass} border-x` : ''
                  }`}
                >
                  {h === desde && desde > 0 ? `≤${h}` : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.chave} className="border-b border-zinc-100 last:border-0">
                <td className="py-1.5 px-1 sticky left-0 bg-white max-w-28 sm:max-w-none">
                  <span className="block truncate" title={l.rotulo}>
                    {l.rotulo}
                  </span>
                  <span className="text-[10px] text-zinc-400">{l.jogos} jogos</span>
                </td>
                {colunas.map((h) => {
                  const obs = valor(l.distrib, h)
                  return (
                    <td
                      key={h}
                      className={`py-1.5 px-1 text-center tabular-nums leading-tight ${
                        premiadas.has(h) ? `${cfg.tintClass} border-x` : ''
                      }`}
                    >
                      <span className={obs ? 'font-semibold' : 'text-zinc-300'}>{obs}</span>
                      <span className="block text-[10px] text-zinc-400">
                        {espTxt(valor(l.distribEsperada, h))}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-zinc-500 mt-3 leading-relaxed">
        Colunas coloridas são as faixas que pagam prêmio. Compare a contagem com o número cinza:
        se uma estratégia tivesse jeito de acertar mais, os jogos dela iriam se acumulando à
        direita do esperado, concurso após concurso. Um jogo isolado numa coluna rara (o cinza
        perto de zero) é sorte daquele sorteio. Com mais jogos, as contagens tendem ao cinza.
      </p>
    </Card>
  )
}

function DesempenhoEstrategias({ dados, cfg, code }) {
  const { linhas, avaliadas } = dados
  const escala = Math.max(...linhas.flatMap((l) => l.ic.map(Math.abs)), 0.1)
  return (
    <Card
      title={`Desempenho por estratégia — ${cfg.nome}`}
      subtitle={`Seus jogos conferidos desta loteria, agrupados pela forma como foram gerados — comparados com o que o acaso entrega para o mesmo número de dezenas`}
    >
      {/* Celular: um bloco por estratégia — a tabela de 8 colunas não cabe. */}
      <div className="sm:hidden divide-y divide-zinc-100">
        {linhas.map((l) => (
          <div key={l.chave} className="py-2 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{l.rotulo}</span>
              <Veredito linha={l} />
            </div>
            <p className="text-[11px] text-zinc-500 tabular-nums">
              {l.jogos} jogos em {l.concursos} conc. · média <strong>{num(l.media)}</strong> · acaso{' '}
              {num(l.esperado)} · prêmios {l.premiados} / {premiosTxt(l)} esp.
            </p>
            <div className="flex items-center gap-2 text-xs tabular-nums">
              <span>
                {sinal(l.diferenca)}
                <span className="text-[11px] text-zinc-400">
                  {' '}
                  ({sinal(l.ic[0])} a {sinal(l.ic[1])})
                </span>
              </span>
              <BarraIC linha={l} escala={escala} />
            </div>
          </div>
        ))}
      </div>
      <div className="hidden sm:block overflow-x-auto -mx-1">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="text-xs text-zinc-500 border-b border-zinc-200">
              <th className="py-1.5 px-1 font-medium">Estratégia</th>
              <th className="py-1.5 px-1 font-medium text-right">Jogos</th>
              <th className="py-1.5 px-1 font-medium text-right">Média</th>
              <th className="py-1.5 px-1 font-medium text-right">Acaso</th>
              <th className="py-1.5 px-1 font-medium text-right">Diferença (IC)</th>
              <th className="py-1.5 px-1 font-medium" />
              <th className="py-1.5 px-1 font-medium text-right">Prêmios</th>
              <th className="py-1.5 px-1 font-medium">Veredito</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.chave} className="border-b border-zinc-100 last:border-0 align-middle">
                <td className="py-1.5 px-1 whitespace-nowrap">{l.rotulo}</td>
                <td className="py-1.5 px-1 text-right tabular-nums text-zinc-600 whitespace-nowrap">
                  {l.jogos}
                  <span className="text-[11px] text-zinc-400"> / {l.concursos} conc.</span>
                </td>
                <td className="py-1.5 px-1 text-right tabular-nums font-semibold">
                  {num(l.media)}
                </td>
                <td className="py-1.5 px-1 text-right tabular-nums text-zinc-500">
                  {num(l.esperado)}
                </td>
                <td className="py-1.5 px-1 text-right tabular-nums whitespace-nowrap">
                  {sinal(l.diferenca)}
                  <span className="text-[11px] text-zinc-400">
                    {' '}
                    ({sinal(l.ic[0])} a {sinal(l.ic[1])})
                  </span>
                </td>
                <td className="py-1.5 px-1">
                  <BarraIC linha={l} escala={escala} />
                </td>
                <td
                  className="py-1.5 px-1 text-right tabular-nums text-zinc-600 whitespace-nowrap"
                  title={`Melhor jogo: ${l.melhor} acertos`}
                >
                  {l.premiados}
                  <span className="text-[11px] text-zinc-400">
                    {' '}
                    / {premiosTxt(l)} esp.
                  </span>
                </td>
                <td className="py-1.5 px-1">
                  <Veredito linha={l} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-zinc-500 mt-3 space-y-1.5 leading-relaxed">
        <p>
          <strong>Diferença</strong> é a média de acertos menos o que o acaso entrega para jogos
          com as mesmas dezenas; o parêntese e a barra mostram o intervalo de 95%. Enquanto a
          barra cruzar o traço do zero, a diferença cabe na sorte da amostra. Jogos do mesmo
          concurso contam como dependentes, porque enfrentaram o mesmo sorteio.
        </p>
        <p>
          Alguma linha sempre fica no topo: com várias estratégias lado a lado, uma delas vai
          estar acima por puro acaso. Por isso o veredito só aparece a partir de {MIN_CONCURSOS}{' '}
          concursos e, com várias estratégias avaliadas, o intervalo é alargado na mesma proporção
          (correção de Bonferroni{avaliadas > 1 ? `, hoje para ${avaliadas} estratégias` : ''}). <strong>Prêmios</strong> conta jogos que chegaram a uma faixa
          paga, ao lado de quantos o acaso daria (esp.).
        </p>
        {cfg.avancada && (
          <p>
            Para uma amostra maior e sem viés de escolha, rode o backtest em{' '}
            <Link to={`/${code}/gerar`} className="text-emerald-700 underline">
              Gerar jogos
            </Link>
            : ele joga cada estratégia nos últimos 50, 100 ou 200 concursos, com 1 a 5 jogos por
            concurso.
          </p>
        )}
      </div>
    </Card>
  )
}

function AcertosBadge({ check }) {
  if (!check?.encontrado) {
    return (
      <span className="text-[11px] text-zinc-400 border border-zinc-200 rounded-full px-2 py-0.5">
        aguardando resultado
      </span>
    )
  }
  return (
    <span
      className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${
        FAIXA_STYLE[check.faixa] ?? 'bg-zinc-100 text-zinc-600'
      }`}
    >
      {check.acertos} acerto(s){check.faixa ? ` · ${check.faixa.toUpperCase()}!` : ''}
    </span>
  )
}

function BetItem({ bet, check, onRemove, cfg }) {
  const matched = check?.encontrado ? new Set(check.resultado) : undefined
  const multipla = bet.dezenas.length > cfg.escolher
  const premios = check?.encontrado ? check.premios ?? [] : []
  return (
    <div className="border border-zinc-200 rounded-lg p-2.5">
      <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <AcertosBadge check={check} />
          {bet.estrategia && (
            <span className="text-[11px] text-zinc-500">estratégia: {bet.estrategia}</span>
          )}
          {typeof bet.espalhar === 'boolean' && (
            <span
              className="text-[11px] text-zinc-500"
              title={
                bet.espalhar_deduzido
                  ? 'Deduzido pelo estudo das dezenas em comum entre os jogos do lote: quando este jogo foi salvo, o app ainda não gravava o Espalhar.'
                  : undefined
              }
            >
              espalhar: {bet.espalhar ? 'ligado' : 'desligado'}
              {bet.espalhar_deduzido ? ' (deduzido)' : ''}
            </span>
          )}
        </div>
        <button
          onClick={() => onRemove(bet.id)}
          title="Excluir jogo"
          className="text-zinc-400 hover:text-red-600 text-sm leading-none"
        >
          ✕
        </button>
      </div>
      <BallRow dezenas={bet.dezenas} size="sm" highlightSet={matched} />
      {multipla && (
        <p className="text-[11px] text-zinc-500 mt-1.5">
          {bet.dezenas.length} dezenas = {comb(bet.dezenas.length, cfg.escolher).toLocaleString('pt-BR')}{' '}
          apostas simples ({reais(comb(bet.dezenas.length, cfg.escolher) * cfg.preco)})
        </p>
      )}
      {multipla && premios.length > 0 && (
        <p className="text-[11px] font-medium text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 mt-1.5">
          Prêmios desta aposta: {premiosTexto(premios)}
          {check.premio_fixo > 0 && <> · {reais(check.premio_fixo)} em faixa de valor fixo</>}
        </p>
      )}
      {check?.encontrado && <Avaliacao av={check.avaliacao} faixa={check.faixa} />}
      <p className="text-[10px] text-zinc-400 mt-1.5">
        registrado em {new Date(bet.criado_em).toLocaleDateString('pt-BR')}
      </p>
    </div>
  )
}

/* Um bolão dentro do concurso: os jogos dele, o custo das apostas e o que o
   bolão inteiro ganhou — e a sua parte, pelas cotas. */
function BolaoBloco({ nome, jogos, checks, cfg, onRemove, onRemoveBolao }) {
  const ref = jogos[jogos.length - 1] // cotas: as do jogo salvo por último
  const { cotas, cotas_total: total } = ref
  const fracao = cotas && total ? cotas / total : null
  const simples = jogos.reduce((s, b) => s + comb(b.dezenas.length, cfg.escolher), 0)
  const conferidos = jogos.map((b) => checks[b.id]).filter((c) => c?.encontrado)
  const premios = somarPremios(conferidos)
  const fixo = premios.reduce((s, p) => s + (p.valor ?? 0), 0)
  const rateio = premios.some((p) => p.valor == null)
  return (
    <div className="border border-emerald-200 rounded-lg p-3 bg-emerald-50/40">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <p className="text-sm font-semibold text-emerald-900">Bolão: {nome}</p>
          <p className="text-[11px] text-zinc-600 mt-0.5">
            {jogos.length} jogo(s) · {simples.toLocaleString('pt-BR')} aposta(s) simples ·{' '}
            {reais(simples * cfg.preco)} em apostas (sem a tarifa da lotérica)
            {fracao != null && (
              <>
                {' '}
                · suas cotas: <strong>{cotas} de {total}</strong> ({num(fracao * 100, fracao * 100 < 10 ? 1 : 0)}%)
              </>
            )}
          </p>
        </div>
        <button
          onClick={() => onRemoveBolao(jogos.map((b) => b.id), nome)}
          className="text-[11px] text-zinc-400 hover:text-red-600 whitespace-nowrap"
        >
          excluir bolão
        </button>
      </div>
      {conferidos.length > 0 && (
        <p
          className={`text-xs rounded px-2 py-1.5 mb-2 border ${
            premios.length
              ? 'bg-emerald-100 border-emerald-300 text-emerald-900 font-medium'
              : 'bg-white border-zinc-200 text-zinc-600'
          }`}
        >
          {premios.length ? (
            <>
              O bolão ganhou: {premiosTexto(premios)}.
              {fixo > 0 && (
                <>
                  {' '}
                  Faixas de valor fixo: {reais(fixo)}
                  {fracao != null && <> — a sua parte é {reais(fixo * fracao)}</>}.
                </>
              )}
              {rateio && (
                <>
                  {' '}
                  O valor de {premios.filter((p) => p.valor == null).map((p) => p.faixa).join(', ')}{' '}
                  depende do rateio do concurso (veja no resultado da Caixa)
                  {fracao != null && <>; você leva {cotas}/{total} do que o bolão receber</>}.
                </>
              )}
            </>
          ) : (
            'Nenhum jogo do bolão chegou a uma faixa premiada.'
          )}
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-2">
        {jogos.map((b) => (
          <BetItem key={b.id} bet={b} check={checks[b.id]} onRemove={onRemove} cfg={cfg} />
        ))}
      </div>
    </div>
  )
}

export default function MeusJogos() {
  const { cfg, code } = useLottery()
  const [bets, setBets] = useState([])
  const [checks, setChecks] = useState({}) // bet.id -> resultado da conferência
  const [status, setStatus] = useState(null)
  const [regua, setRegua] = useState(null) // distribuição de acertos da aposta simples
  const [concurso, setConcurso] = useState('')
  const [dezenas, setDezenas] = useState([])
  // Formulário: 'manual' = jogo seu; 'bolao' = jogos de um bolão, com cotas.
  const [tipo, setTipo] = useState('manual')
  const [bolaoNome, setBolaoNome] = useState('')
  const [cotas, setCotas] = useState('')
  const [cotasTotal, setCotasTotal] = useState('')
  const [colado, setColado] = useState('')
  const [message, setMessage] = useState(null)
  const [session, setSession] = useState(getSession())
  const [emailInput, setEmailInput] = useState('')
  const [authBusy, setAuthBusy] = useState(false)
  const [linkColado, setLinkColado] = useState('')
  // Resultado da última sincronização: { ok: true, n } ou { ok: false, texto }.
  // Antes a falha era engolida e a tela seguia dizendo "conectado" enquanto
  // nada chegava à nuvem — o celular abria vazio sem nenhum aviso.
  const [sync, setSync] = useState(null)
  const fileRef = useRef(null)

  const refresh = useCallback(async () => {
    if (getSession()) {
      try {
        const nuvem = await syncBets(code) // traz jogos de outros aparelhos e migra os locais
        setSync({ ok: true, n: nuvem.length })
      } catch (e) {
        if (e.status === 401) {
          // O servidor não reconhece mais a sessão (expirou ou o banco a
          // perdeu). Sair de verdade, para o formulário de login aparecer.
          clearSession()
          setSession(null)
          setSync({
            ok: false,
            texto:
              'Sua sessão não vale mais no servidor, então os jogos deste aparelho não estavam indo para a nuvem. Entre de novo abaixo: os jogos salvos aqui sobem para a conta assim que você entrar.',
          })
        } else {
          setSync({
            ok: false,
            texto: `Não foi possível sincronizar com a nuvem (${e.message || 'sem rede'}). Os jogos deste aparelho continuam salvos aqui e sobem na próxima sincronização.`,
          })
        }
      }
    } else {
      setSync(null)
    }
    const list = loadBets(code)
    setBets(list)
    if (list.length === 0) return
    try {
      const r = await apiPost('/check', {
        apostas: list.map((b) => ({ concurso: b.concurso, dezenas: b.dezenas })),
      })
      const map = {}
      list.forEach((b, i) => {
        map[b.id] = r.resultados[i]
      })
      setChecks(map)
    } catch {
      // backend fora do ar: mostra os jogos sem conferência
      setChecks({})
    }
  }, [code])

  useEffect(() => {
    apiGet('/acertos-esperados')
      .then(setRegua)
      .catch(() => setRegua(null))
  }, [code])

  // Sorteio novo gravado em segundo plano: confere os jogos de novo.
  useEffect(() => {
    const atualizar = () => refresh()
    window.addEventListener(EVENTO_SORTEIOS, atualizar)
    return () => window.removeEventListener(EVENTO_SORTEIOS, atualizar)
  }, [refresh])

  useEffect(() => {
    refresh()
    apiGet('/status')
      .then((st) => {
        setStatus(st)
        const prox = st.proximo?.concurso ?? (st.ultimo_local ? st.ultimo_local.concurso + 1 : '')
        setConcurso((c) => c || prox)
      })
      .catch(() => {})
  }, [refresh])

  // Bolões já salvos no concurso do formulário: sugestões de nome, e as
  // cotas de um bolão existente vêm preenchidas ao escolher o nome dele.
  const boloesDoConcurso = useMemo(() => {
    const por = new Map()
    for (const b of bets) {
      if (b.origem === 'bolao' && b.concurso === Number(concurso)) por.set(b.bolao, b)
    }
    return por
  }, [bets, concurso])
  const bolaoExistente = boloesDoConcurso.get(bolaoNome.trim())

  function escolherBolao(nome) {
    setBolaoNome(nome)
    const b = boloesDoConcurso.get(nome.trim())
    if (b) {
      setCotas(b.cotas ?? '')
      setCotasTotal(b.cotas_total ?? '')
    }
  }

  const cotasInvalidas = Boolean(cotas && cotasTotal && Number(cotas) > Number(cotasTotal))
  const formOk = Boolean(concurso) && (tipo === 'manual' || (bolaoNome.trim() && !cotasInvalidas))

  function salvarJogos(lista) {
    if (!formOk || lista.length === 0) return
    const extra =
      tipo === 'bolao'
        ? { bolao: bolaoNome.trim(), cotas: cotas || null, cotas_total: cotasTotal || null }
        : {}
    addBets(
      code,
      lista.map((dz) => ({ concurso, origem: tipo, dezenas: dz, ...extra })),
    )
    const qtd = lista.length === 1 ? 'Jogo salvo' : `${lista.length} jogos salvos`
    setMessage({
      type: 'ok',
      text:
        tipo === 'bolao'
          ? `${qtd} no bolão “${bolaoNome.trim()}”, concurso ${concurso}.`
          : `${qtd} no concurso ${concurso}.`,
    })
    refresh()
  }

  function salvarVolante() {
    if (dezenas.length < cfg.escolher) return
    salvarJogos([dezenas])
    setDezenas([])
  }

  const lidos = useMemo(() => lerJogos(colado, cfg), [colado, cfg])

  function salvarColados() {
    if (lidos.erros.length || lidos.jogos.length === 0) return
    salvarJogos(lidos.jogos)
    setColado('')
  }

  function remover(id) {
    removeBet(code, id)
    refresh()
  }

  function removerBolao(ids, nome) {
    if (!window.confirm(`Excluir o bolão “${nome}” e os ${ids.length} jogo(s) dele?`)) return
    removeBets(code, ids)
    refresh()
  }

  const simplesVolante = comb(dezenas.length, cfg.escolher)

  async function importar(file) {
    if (!file) return
    try {
      const r = await importBets(file, code)
      setMessage({
        type: 'ok',
        text: r.ignorados
          ? `Backup importado: ${r.importados} jogo(s). ${r.ignorados} ignorado(s) por não estarem no formato da ${cfg.nome} (${cfg.escolher} a ${cfg.maxEscolher} dezenas de ${cfg.min} a ${cfg.max}).`
          : `Backup importado: ${r.importados} jogo(s).`,
      })
      refresh()
    } catch (e) {
      setMessage({ type: 'error', text: `Falha ao importar: ${e.message}` })
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function enviarLink(e) {
    e.preventDefault()
    const email = emailInput.trim()
    if (!email) return
    setAuthBusy(true)
    try {
      const r = await requestLink(email)
      if (r.status === 'ok') {
        setMessage({
          type: 'ok',
          text: 'Se este e-mail tiver acesso, você receberá um link para entrar. Verifique a caixa de entrada e o spam.',
        })
        setEmailInput('')
      } else {
        setMessage({ type: 'error', text: r.message || 'Não foi possível enviar o link.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Falha de rede ao pedir o link.' })
    } finally {
      setAuthBusy(false)
    }
  }

  async function entrarComLink(e) {
    e.preventDefault()
    const token = extrairToken(linkColado)
    if (!token) {
      setMessage({ type: 'error', text: 'Isso não parece o link de acesso. Cole o link inteiro do e-mail.' })
      return
    }
    setAuthBusy(true)
    try {
      const r = await verifyToken(token)
      if (r.status === 'success') {
        setSession(getSession())
        setLinkColado('')
        setMessage({ type: 'ok', text: `Conectado como ${r.email}.` })
        refresh()
      } else {
        setMessage({ type: 'error', text: r.message || 'Link inválido. Peça um novo.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Falha de rede ao validar o link.' })
    } finally {
      setAuthBusy(false)
    }
  }

  async function sair() {
    await logout()
    setSession(null)
    setMessage({ type: 'ok', text: 'Você saiu. Os jogos continuam salvos neste navegador.' })
  }

  const grupos = useMemo(() => {
    const by = new Map()
    for (const b of bets) {
      if (!by.has(b.concurso)) by.set(b.concurso, [])
      by.get(b.concurso).push(b)
    }
    return [...by.entries()].sort((a, b) => b[0] - a[0])
  }, [bets])

  const comparativo = useMemo(() => {
    const manuais = bets.filter((b) => checks[b.id]?.encontrado && b.origem === 'manual')
    const doApp = bets.filter((b) => checks[b.id]?.encontrado && b.origem === 'app')
    if (manuais.length === 0 && doApp.length === 0) return null
    const media = (list) =>
      list.length ? list.reduce((s, b) => s + checks[b.id].acertos, 0) / list.length : null

    let vitoriasManual = 0
    let vitoriasApp = 0
    let empates = 0
    for (const [, grupo] of grupos) {
      const m = grupo.filter((b) => b.origem === 'manual' && checks[b.id]?.encontrado)
      const a = grupo.filter((b) => b.origem === 'app' && checks[b.id]?.encontrado)
      if (m.length === 0 || a.length === 0) continue
      const bm = Math.max(...m.map((b) => checks[b.id].acertos))
      const ba = Math.max(...a.map((b) => checks[b.id].acertos))
      if (bm > ba) vitoriasManual++
      else if (ba > bm) vitoriasApp++
      else empates++
    }
    return {
      mediaManual: media(manuais),
      mediaApp: media(doApp),
      qtdManual: manuais.length,
      qtdApp: doApp.length,
      vitoriasManual,
      vitoriasApp,
      empates,
      confrontos: vitoriasManual + vitoriasApp + empates,
    }
  }, [bets, checks, grupos])

  // `bets` só contém jogos da loteria aberta (cada uma tem sua chave no
  // navegador e na nuvem), então Mega e Lotofácil nunca se misturam aqui.
  const desempenho = useMemo(() => desempenhoPorEstrategia(bets, checks, cfg), [bets, checks, cfg])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Meus jogos</h2>
        <div className="flex gap-2">
          <button
            onClick={() => exportBets(code)}
            disabled={bets.length === 0}
            className="px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-xs font-medium hover:bg-zinc-50 disabled:opacity-50"
          >
            Exportar backup
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            className="px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-xs font-medium hover:bg-zinc-50"
          >
            Importar backup
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => importar(e.target.files?.[0])}
          />
        </div>
      </div>

      <Card
        title="Sincronizar entre aparelhos"
        subtitle={
          session
            ? 'Seus jogos são salvos na sua conta e aparecem em qualquer aparelho.'
            : 'Entre com seu e-mail para ver os mesmos jogos no celular e no computador.'
        }
      >
        {session ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-zinc-600">
              Conectado como <strong>{session.email}</strong>.{' '}
              {sync?.ok
                ? `${sync.n} jogo(s) da ${cfg.nome} na sua conta.`
                : 'Os jogos sincronizam automaticamente.'}
            </p>
            <button
              onClick={sair}
              className="px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-xs font-medium hover:bg-zinc-50"
            >
              Sair
            </button>
          </div>
        ) : (
          <form onSubmit={enviarLink} className="space-y-2">
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="email"
                required
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                placeholder="seu@email.com"
                className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={authBusy || !emailInput.trim()}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
              >
                {authBusy ? 'Enviando…' : 'Enviar link de acesso'}
              </button>
            </div>
            <p className="text-[11px] text-zinc-500">
              Você recebe um link no e-mail e entra sem senha. Ao entrar, os jogos que já estão
              neste navegador são enviados para a sua conta (nada é perdido).
            </p>
          </form>
        )}
        {!session && (
          <form onSubmit={entrarComLink} className="mt-3 pt-3 border-t border-zinc-100 space-y-2">
            <p className="text-[11px] text-zinc-500">
              <strong>No celular:</strong> o link do e-mail costuma abrir dentro do app de e-mail,
              e o login fica preso lá. Em vez de tocar no botão, toque e segure, escolha{' '}
              <em>Copiar link</em> e cole aqui:
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={linkColado}
                onChange={(e) => setLinkColado(e.target.value)}
                placeholder="cole o link de acesso"
                className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={authBusy || !linkColado.trim()}
                className="px-4 py-2 rounded-lg border border-emerald-600 text-emerald-700 text-sm font-semibold hover:bg-emerald-50 disabled:opacity-50"
              >
                Entrar com o link
              </button>
            </div>
          </form>
        )}
        {sync && !sync.ok && (
          <p className="mt-3 text-sm rounded-lg px-3 py-2 border bg-amber-50 border-amber-200 text-amber-800">
            {sync.texto}
          </p>
        )}
        {session && status?.db_backend === 'sqlite' && !['localhost', '127.0.0.1'].includes(window.location.hostname) && (
          <p className="mt-3 text-sm rounded-lg px-3 py-2 border bg-amber-50 border-amber-200 text-amber-800">
            O servidor está sem banco de dados persistente (Turso não configurado): o login e os
            jogos na nuvem se perdem a cada reinício. Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN
            na Vercel.
          </p>
        )}
      </Card>

      <p className="text-xs text-zinc-500">
        {session
          ? 'Os jogos ficam na sua conta (nuvem) e também neste navegador. '
          : 'Os jogos ficam salvos neste navegador. Use o backup ou o login acima para levar para outro aparelho. '}
        O “jogo do app” é salvo pela tela{' '}
        <Link to={`/${code}/gerar`} className="text-emerald-700 underline">
          Gerar jogos
        </Link>
        .
      </p>

      {message && (
        <p
          className={`text-sm rounded-lg px-3 py-2 border ${
            message.type === 'ok'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {message.text}
        </p>
      )}

      <Card
        title="Adicionar jogo para conferir"
        subtitle={`Seu jogo ou os jogos de um bolão — simples ou múltipla, de ${cfg.escolher} a ${cfg.maxEscolher} dezenas por jogo`}
      >
        <div className="flex flex-wrap items-center gap-2 mb-3" role="tablist">
          {[
            ['manual', 'Meu jogo'],
            ['bolao', 'Bolão'],
          ].map(([v, rot]) => (
            <button
              key={v}
              role="tab"
              aria-selected={tipo === v}
              onClick={() => setTipo(v)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${
                tipo === v
                  ? 'bg-emerald-600 border-emerald-600 text-white'
                  : 'bg-white border-zinc-300 text-zinc-700 hover:bg-zinc-50'
              }`}
            >
              {rot}
            </button>
          ))}
          <span className="text-[11px] text-zinc-500">
            {tipo === 'manual'
              ? 'dezenas que VOCÊ escolheu (entram no comparativo você vs. app)'
              : 'jogos de um bolão — ficam agrupados, com as suas cotas'}
          </span>
        </div>

        {tipo === 'bolao' && (
          <div className="grid grid-cols-2 sm:grid-cols-[1fr_auto_auto] gap-2 mb-3 items-end">
            <label className="text-sm col-span-2 sm:col-span-1">
              <span className="text-zinc-600">Nome do bolão</span>
              <input
                type="text"
                list="boloes-do-concurso"
                maxLength={60}
                value={bolaoNome}
                onChange={(e) => escolherBolao(e.target.value)}
                placeholder="ex.: Bolão do trabalho"
                className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5"
              />
              <datalist id="boloes-do-concurso">
                {[...boloesDoConcurso.keys()].map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
            </label>
            <label className="text-sm">
              <span className="text-zinc-600">Suas cotas</span>
              <input
                type="number"
                min="1"
                value={cotas}
                onChange={(e) => setCotas(e.target.value)}
                placeholder="1"
                className="mt-1 w-full sm:w-24 border border-zinc-300 rounded-lg px-2 py-1.5"
              />
            </label>
            <label className="text-sm">
              <span className="text-zinc-600">Total de cotas</span>
              <input
                type="number"
                min="1"
                value={cotasTotal}
                onChange={(e) => setCotasTotal(e.target.value)}
                placeholder="10"
                className="mt-1 w-full sm:w-24 border border-zinc-300 rounded-lg px-2 py-1.5"
              />
            </label>
            <p className="text-[11px] text-zinc-500 col-span-2 sm:col-span-3">
              {cotasInvalidas ? (
                <span className="text-red-600">Suas cotas não podem passar do total.</span>
              ) : bolaoExistente ? (
                <>Este bolão já existe no concurso {concurso}: os jogos novos entram nele.</>
              ) : (
                <>
                  As cotas são opcionais — com elas o app calcula a sua parte do prêmio. Salve
                  quantos jogos o bolão tiver: com o mesmo nome, todos ficam juntos.
                </>
              )}
            </p>
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-4">
          <div>
            <Volante selected={dezenas} onChange={setDezenas} max={cfg.maxEscolher} />
          </div>
          <div className="space-y-3 min-w-48">
            <label className="text-sm block">
              <span className="text-zinc-600">Concurso</span>
              <input
                type="number"
                min="1"
                value={concurso}
                onChange={(e) => setConcurso(e.target.value)}
                className="mt-1 w-full border border-zinc-300 rounded-lg px-2 py-1.5"
              />
              {status?.proximo?.concurso && Number(concurso) === status.proximo.concurso && (
                <span className="text-[11px] text-emerald-700">próximo a fechar</span>
              )}
            </label>
            <div className="text-sm">
              <span className="text-zinc-600">
                Selecionadas ({dezenas.length}/{cfg.escolher}
                {cfg.maxEscolher > cfg.escolher ? `–${cfg.maxEscolher}` : ''}):
              </span>
              <div className="mt-1 min-h-8">
                {dezenas.length > 0 ? (
                  <BallRow dezenas={dezenas} size="sm" />
                ) : (
                  <span className="text-xs text-zinc-400">toque nos números do volante</span>
                )}
              </div>
              {dezenas.length > cfg.escolher && (
                <p className="text-[11px] text-zinc-500 mt-1">
                  Aposta múltipla: {simplesVolante.toLocaleString('pt-BR')} apostas simples ·{' '}
                  {reais(simplesVolante * cfg.preco)}
                </p>
              )}
            </div>
            <button
              onClick={salvarVolante}
              disabled={dezenas.length < cfg.escolher || !formOk}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
            >
              {tipo === 'bolao' ? 'Adicionar ao bolão' : 'Salvar meu jogo'}
            </button>
          </div>
        </div>

        <details className="mt-4 border-t border-zinc-100 pt-3" open={tipo === 'bolao' || undefined}>
          <summary className="text-sm font-medium text-zinc-700 cursor-pointer">
            Colar vários jogos de uma vez
          </summary>
          <p className="text-[11px] text-zinc-500 mt-1.5">
            Um jogo por linha, com {cfg.escolher} a {cfg.maxEscolher} dezenas. Vale copiar do
            comprovante do bolão: “Jogo 1: 04 11 23 35 42 58” ou “4, 11, 23, 35, 42, 58”.
          </p>
          <textarea
            value={colado}
            onChange={(e) => setColado(e.target.value)}
            rows={4}
            placeholder={
              cfg.escolher === 6 ? '04 11 23 35 42 58\n02 09 17 30 44 51 60' : 'uma linha por jogo'
            }
            className="mt-2 w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm font-mono"
          />
          {lidos.erros.length > 0 && (
            <ul className="text-[11px] text-red-600 mt-1 space-y-0.5">
              {lidos.erros.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          <button
            onClick={salvarColados}
            disabled={!formOk || lidos.erros.length > 0 || lidos.jogos.length === 0}
            className="mt-2 px-4 py-2 rounded-lg border border-emerald-600 text-emerald-700 text-sm font-semibold hover:bg-emerald-50 disabled:opacity-50"
          >
            Salvar {lidos.jogos.length || ''} jogo(s)
            {tipo === 'bolao' ? ' no bolão' : ''}
          </button>
          {tipo === 'bolao' && !bolaoNome.trim() && (
            <span className="text-[11px] text-zinc-500 ml-2">dê um nome ao bolão acima</span>
          )}
        </details>
      </Card>

      {regua && (() => {
        // Escala das barras: a maior probabilidade da distribuição (a moda),
        // não a primeira linha — `linhas` vem em ordem de acertos.
        const maxPct = Math.max(...regua.linhas.map((l) => l.pct))
        return (
        <Card
          title={`Quantos acertos esperar de um jogo de ${regua.dezenas} dezenas`}
          subtitle={`Média ${num(regua.esperado, 1)} acertos · a régua para saber se um resultado foi bom, ruim ou apenas normal`}
        >
          <div className="space-y-1">
            {regua.linhas
              .filter((l) => l.pct >= 0.01 || l.faixa)
              .sort((a, b) => b.acertos - a.acertos)
              .map((l) => (
                <div key={l.acertos} className="flex items-center gap-2 text-[11px]">
                  <span className="w-6 text-right tabular-nums font-semibold text-zinc-600">
                    {l.acertos}
                  </span>
                  <div className="flex-1 flex items-center gap-1.5">
                    <div
                      className={`h-3 rounded-sm min-w-[2px] ${
                        l.faixa ? cfg.barClass : 'bg-zinc-300'
                      }`}
                      style={{ width: `${(l.pct / maxPct) * 100 || 0}%` }}
                      title={`${l.pct}%`}
                    />
                    <span className="tabular-nums text-zinc-500">
                      {l.pct >= 0.01 ? `${num(l.pct, 2)}%` : '~0%'}
                    </span>
                    {l.faixa && (
                      <span className="text-zinc-400">
                        · paga prêmio ({l.faixa})
                      </span>
                    )}
                  </div>
                </div>
              ))}
          </div>
          <p className="text-xs text-zinc-600 mt-3 leading-relaxed">
            O mais provável é <strong>{regua.mais_provavel} acertos</strong>, e a chance de chegar à
            faixa mínima ({regua.menor_faixa_premiada} acertos) é de{' '}
            <strong>{num(regua.premiado.pct, 1)}%</strong> — 1 em {regua.premiado.one_in}. Isso vale
            para qualquer combinação, gerada pelo app ou escolhida por você: barras coloridas são as
            faixas que pagam, e é só nelas que o dinheiro volta.
          </p>
          <p className="text-xs text-zinc-500 mt-2 leading-relaxed border-t border-zinc-100 pt-2">
            Para <strong>subir os acertos</strong> não existe estratégia — existem duas alavancas, e
            as duas custam na mesma proporção: marcar mais dezenas no bilhete (cada dezena a mais
            sobe a média em {num(cfg.sorteadas / cfg.total, 1)} acerto) ou jogar mais bilhetes. Veja
            os dois preços em{' '}
            <Link to={`/${code}/probabilidades`} className="text-emerald-700 underline">
              Probabilidades
            </Link>
            .
          </p>
        </Card>
        )
      })()}

      {cfg.premios && (
        <Card
          title={`Faixas premiadas — ${cfg.nome}`}
          subtitle="Quantos acertos pagam prêmio (o app destaca os acertos ao conferir seus jogos abaixo)"
        >
          <div className="flex flex-wrap gap-2">
            {cfg.premios.map((p) => (
              <div
                key={p.ac}
                className="flex items-center gap-2 border border-zinc-200 rounded-lg px-3 py-1.5 text-sm"
              >
                <span className="font-semibold tabular-nums">{p.ac} acerto(s)</span>
                <span className="text-zinc-400">·</span>
                <span className="text-zinc-600">{p.label}</span>
              </div>
            ))}
          </div>
          {!cfg.avancada && (
            <p className="text-[11px] text-zinc-500 mt-2">
              Abaixo de 15 acertos não há prêmio (e, curiosamente, acertar 0 paga tanto quanto uma
              faixa alta). Os % são a fatia do prêmio total destinada a cada faixa.
            </p>
          )}
        </Card>
      )}

      {comparativo && comparativo.confrontos > 0 && (
        <Card
          title="Comparativo: você vs. app"
          subtitle="Só por curiosidade — no longo prazo, a estatística diz que isso tende ao empate"
        >
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xl font-bold tabular-nums">
                {comparativo.mediaManual?.toFixed(2) ?? '—'}
              </p>
              <p className="text-xs text-zinc-500">média de acertos — manual ({comparativo.qtdManual} jogos)</p>
            </div>
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xl font-bold tabular-nums">
                {comparativo.mediaApp?.toFixed(2) ?? '—'}
              </p>
              <p className="text-xs text-zinc-500">média de acertos — app ({comparativo.qtdApp} jogos)</p>
            </div>
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xl font-bold tabular-nums">
                {comparativo.vitoriasManual} × {comparativo.vitoriasApp}
              </p>
              <p className="text-xs text-zinc-500">vitórias manual × app (por concurso)</p>
            </div>
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xl font-bold tabular-nums">{comparativo.empates}</p>
              <p className="text-xs text-zinc-500">empates</p>
            </div>
          </div>
        </Card>
      )}

      {desempenho.linhas.length > 0 && (
        <>
          <DistribuicaoAcertos linhas={desempenho.linhas} cfg={cfg} />
          <DesempenhoEstrategias dados={desempenho} cfg={cfg} code={code} />
        </>
      )}

      {grupos.length === 0 ? (
        <Card>
          <p className="text-sm text-zinc-500">
            Nenhum jogo salvo ainda. Adicione seu jogo ou bolão acima e gere o jogo do app em{' '}
            <Link to={`/${code}/gerar`} className="text-emerald-700 underline">
              Gerar jogos
            </Link>
            .
          </p>
        </Card>
      ) : (
        grupos.map(([conc, grupo]) => {
          const anyCheck = grupo.map((b) => checks[b.id]).find((c) => c?.encontrado)
          return (
            <Card
              key={conc}
              title={`Concurso ${conc}`}
              subtitle={
                anyCheck
                  ? `resultado de ${formatDate(anyCheck.data)}`
                  : 'resultado ainda não sincronizado — vá em Sorteios e clique em “Sincronizar”'
              }
            >
              {anyCheck && (
                <div className="mb-3 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-zinc-500">Sorteado:</span>
                  <BallRow dezenas={anyCheck.resultado} size="sm" />
                </div>
              )}
              {grupo.some((b) => b.origem !== 'bolao') && (
              <div className="grid sm:grid-cols-2 gap-3">
                {['manual', 'app'].map((origem) => {
                  const doGrupo = grupo.filter((b) => b.origem === origem)
                  return (
                    <div key={origem}>
                      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-1.5">
                        {ORIGEM_LABEL[origem]}
                      </p>
                      {doGrupo.length === 0 ? (
                        <p className="text-xs text-zinc-400 border border-dashed border-zinc-200 rounded-lg p-3">
                          {origem === 'manual'
                            ? 'sem jogo manual neste concurso'
                            : 'sem jogo do app neste concurso'}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {doGrupo.map((b) => (
                            <BetItem key={b.id} bet={b} check={checks[b.id]} onRemove={remover} cfg={cfg} />
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
              )}
              {boloesDe(grupo).map(([nome, jogos]) => (
                <div key={nome} className="mt-3">
                  <BolaoBloco
                    nome={nome}
                    jogos={jogos}
                    checks={checks}
                    cfg={cfg}
                    onRemove={remover}
                    onRemoveBolao={removerBolao}
                  />
                </div>
              ))}
            </Card>
          )
        })
      )}
    </div>
  )
}
