import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api.js'
import { addBet, exportBets, importBets, loadBets, removeBet, syncBets } from '../lib/bets.js'
import { getSession, logout, requestLink } from '../lib/auth.js'
import { useLottery } from '../lib/LotteryContext.jsx'
import { BallRow } from '../components/Ball.jsx'
import Card from '../components/Card.jsx'
import Volante from '../components/Volante.jsx'
import { formatDate } from '../lib/format.js'

const FAIXA_STYLE = {
  sena: 'bg-emerald-600 text-white',
  quina: 'bg-amber-500 text-white',
  quadra: 'bg-blue-600 text-white',
}

const ORIGEM_LABEL = { manual: 'Meu jogo (manual)', app: 'Jogo do app' }

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

function BetItem({ bet, check, onRemove }) {
  const matched = check?.encontrado ? new Set(check.resultado) : undefined
  return (
    <div className="border border-zinc-200 rounded-lg p-2.5">
      <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <AcertosBadge check={check} />
          {bet.estrategia && (
            <span className="text-[11px] text-zinc-500">estratégia: {bet.estrategia}</span>
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
      <p className="text-[10px] text-zinc-400 mt-1.5">
        registrado em {new Date(bet.criado_em).toLocaleDateString('pt-BR')}
      </p>
    </div>
  )
}

export default function MeusJogos() {
  const { cfg, code } = useLottery()
  const [bets, setBets] = useState([])
  const [checks, setChecks] = useState({}) // bet.id -> resultado da conferência
  const [status, setStatus] = useState(null)
  const [concurso, setConcurso] = useState('')
  const [dezenas, setDezenas] = useState([])
  const [message, setMessage] = useState(null)
  const [session, setSession] = useState(getSession())
  const [emailInput, setEmailInput] = useState('')
  const [authBusy, setAuthBusy] = useState(false)
  const fileRef = useRef(null)

  const refresh = useCallback(async () => {
    if (getSession()) {
      try {
        await syncBets(code) // traz jogos de outros aparelhos e migra os locais
      } catch {
        // sem rede/sessão expirada: segue com o que está no navegador
      }
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
    refresh()
    apiGet('/status')
      .then((st) => {
        setStatus(st)
        const prox = st.proximo?.concurso ?? (st.ultimo_local ? st.ultimo_local.concurso + 1 : '')
        setConcurso((c) => c || prox)
      })
      .catch(() => {})
  }, [refresh])

  function salvarManual() {
    if (dezenas.length !== cfg.escolher || !concurso) return
    addBet({ loteria: code, concurso, origem: 'manual', dezenas })
    setDezenas([])
    setMessage({ type: 'ok', text: `Jogo manual salvo no concurso ${concurso}.` })
    refresh()
  }

  function remover(id) {
    removeBet(code, id)
    refresh()
  }

  async function importar(file) {
    if (!file) return
    try {
      const r = await importBets(file, code)
      setMessage({ type: 'ok', text: `Backup importado: ${r.importados} jogo(s).` })
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
              Conectado como <strong>{session.email}</strong>. Os jogos sincronizam
              automaticamente.
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
        title="Adicionar meu jogo (manual)"
        subtitle={`Marque as ${cfg.escolher} dezenas que VOCÊ escolheu (de qualquer fonte) e vincule ao concurso`}
      >
        <div className="flex flex-col sm:flex-row gap-4">
          <div>
            <Volante selected={dezenas} onChange={setDezenas} max={cfg.escolher} />
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
                Selecionadas ({dezenas.length}/{cfg.escolher}):
              </span>
              <div className="mt-1 min-h-8">
                {dezenas.length > 0 ? (
                  <BallRow dezenas={dezenas} size="sm" />
                ) : (
                  <span className="text-xs text-zinc-400">toque nos números do volante</span>
                )}
              </div>
            </div>
            <button
              onClick={salvarManual}
              disabled={dezenas.length !== cfg.escolher || !concurso}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
            >
              Salvar meu jogo
            </button>
          </div>
        </div>
      </Card>

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

      {grupos.length === 0 ? (
        <Card>
          <p className="text-sm text-zinc-500">
            Nenhum jogo salvo ainda. Adicione seu jogo manual acima e gere o jogo do app em{' '}
            <Link to="/gerar" className="text-emerald-700 underline">
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
                            <BetItem key={b.id} bet={b} check={checks[b.id]} onRemove={remover} />
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </Card>
          )
        })
      )}
    </div>
  )
}
