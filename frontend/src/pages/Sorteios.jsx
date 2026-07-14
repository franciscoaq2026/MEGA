import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet, apiPost, apiUpload } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import { formatDate } from '../lib/format.js'

const PAGE = 24

// Fontes oficiais acessadas DIRETO do navegador do usuário. A Caixa/guidi
// bloqueiam IPs de datacenter (o servidor no Vercel), mas não o IP residencial
// de quem usa o site — então os concursos mais novos entram por aqui.
const FONTES_DIRETAS = [
  {
    nome: 'Caixa',
    url: (n) =>
      n
        ? `https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/${n}`
        : 'https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena',
  },
  {
    nome: 'guidi',
    url: (n) =>
      n
        ? `https://api.guidi.dev.br/loteria/megasena/${n}`
        : 'https://api.guidi.dev.br/loteria/megasena/ultimo',
  },
]

async function fetchDireto(url) {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), 12000)
  try {
    const res = await fetch(url, { signal: ctl.signal, headers: { Accept: 'application/json' } })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } finally {
    clearTimeout(t)
  }
}

// Busca do navegador os concursos que faltam depois do último salvo e envia
// os payloads brutos ao backend (/import-payloads), que valida e grava.
async function sincronizarPeloNavegador(ultimoLocal, apiPostFn, onProgress) {
  for (const fonte of FONTES_DIRETAS) {
    try {
      const ultimo = await fetchDireto(fonte.url())
      const numUltimo = Number(ultimo.numero ?? ultimo.concurso)
      if (!Number.isFinite(numUltimo) || numUltimo <= ultimoLocal) {
        return { fonte: fonte.nome, enviados: 0, atualRemoto: numUltimo || ultimoLocal }
      }
      const faltando = []
      for (let n = ultimoLocal + 1; n < numUltimo; n++) faltando.push(n)
      const alvoTotal = faltando.length + 1

      let payloads = [ultimo]
      let enviados = 0
      const flush = async () => {
        if (!payloads.length) return
        const r = await apiPostFn('/import-payloads', { payloads })
        enviados += r.added
        payloads = []
        onProgress(enviados, alvoTotal)
      }

      for (let i = 0; i < faltando.length; i += 10) {
        const lote = faltando.slice(i, i + 10)
        const res = await Promise.allSettled(lote.map((n) => fetchDireto(fonte.url(n))))
        payloads.push(...res.filter((r) => r.status === 'fulfilled').map((r) => r.value))
        if (payloads.length >= 25) await flush()
      }
      await flush()
      return { fonte: fonte.nome, enviados, atualRemoto: numUltimo }
    } catch {
      // CORS ou rede: tenta a próxima fonte; se todas falharem, retorna null
    }
  }
  return null
}

export default function Sorteios() {
  const [status, setStatus] = useState(null)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [sync, setSync] = useState(null) // {added, remaining} durante a sincronização
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null) // {type: 'ok'|'error', text}
  const fileRef = useRef(null)

  const reload = useCallback(async () => {
    const [st, dr] = await Promise.all([apiGet('/status'), apiGet(`/draws?limit=${PAGE}`)])
    setStatus(st)
    setItems(dr.items)
    setTotal(dr.total)
  }, [])

  useEffect(() => {
    reload().catch((e) => setMessage({ type: 'error', text: e.message }))
  }, [reload])

  async function loadMore() {
    const dr = await apiGet(`/draws?limit=${PAGE}&offset=${items.length}`)
    setItems((prev) => [...prev, ...dr.items])
    setTotal(dr.total)
  }

  async function syncAll() {
    setBusy(true)
    setMessage(null)
    let added = 0
    try {
      // Fase 1 — servidor: seed embutido + espelhos (rápido, cobre o histórico)
      for (;;) {
        const r = await apiPost('/sync')
        added += r.added
        setSync({ added, remaining: r.remaining, fase: 'servidor' })
        if (r.remaining <= 0) break
      }

      // Fase 2 — navegador: busca na Caixa (pelo SEU IP, que não é bloqueado)
      // os concursos mais novos que nenhuma fonte de servidor tem ainda
      const st = await apiGet('/status')
      const ultimoLocal = st.ultimo_local?.concurso ?? 0
      let direto = null
      if (ultimoLocal > 0) {
        setSync({ added, remaining: 0, fase: 'navegador' })
        direto = await sincronizarPeloNavegador(ultimoLocal, apiPost, (env, alvo) =>
          setSync({ added: added + env, remaining: Math.max(alvo - env, 0), fase: 'navegador' }),
        )
      }

      const totalNovo = added + (direto?.enviados ?? 0)
      if (direto) {
        setMessage({
          type: 'ok',
          text:
            direto.enviados > 0
              ? `Sincronizado: ${totalNovo} concurso(s) novo(s) — ${direto.enviados} vindo(s) da ${direto.fonte} direto pelo seu navegador. Tudo atualizado até o concurso ${direto.atualRemoto}.`
              : `Sincronizado: ${totalNovo} concurso(s) novo(s). Você já está no concurso mais recente (${direto.atualRemoto}).`,
        })
      } else {
        setMessage({
          type: 'ok',
          text: `Sincronizado: ${totalNovo} concurso(s) novo(s). Não consegui consultar a Caixa pelo navegador (rede/CORS) — os dados vão até o espelho mais recente disponível.`,
        })
      }
      await reload()
    } catch (e) {
      setMessage({
        type: 'error',
        text: `${e.message} — se as APIs estiverem fora do ar, use a importação de CSV abaixo.`,
      })
    } finally {
      setBusy(false)
      setSync(null)
    }
  }

  async function importCsv(file) {
    if (!file) return
    setBusy(true)
    setMessage(null)
    try {
      const r = await apiUpload('/import-csv', file)
      setMessage({
        type: 'ok',
        text: `CSV importado: ${r.imported} sorteio(s)${r.skipped ? `, ${r.skipped} linha(s) ignorada(s)` : ''}.`,
      })
      await reload()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Sorteios</h2>
          <p className="text-sm text-zinc-500">
            {status
              ? status.total_draws > 0
                ? `${status.total_draws} concursos no cache local · último: ${status.ultimo_local.concurso} (${formatDate(status.ultimo_local.data)})`
                : 'Nenhum sorteio no cache ainda — sincronize ou importe um CSV.'
              : 'Carregando…'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={syncAll}
            disabled={busy}
            className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {sync
              ? sync.fase === 'navegador'
                ? `Buscando novos na Caixa… ${sync.added} baixados${sync.remaining ? `, faltam ~${sync.remaining}` : ''}`
                : `Sincronizando… ${sync.added} baixados, faltam ${sync.remaining}`
              : 'Sincronizar sorteios'}
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="px-4 py-2 rounded-lg border border-zinc-300 bg-white text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
          >
            Importar CSV
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => importCsv(e.target.files?.[0])}
          />
        </div>
      </div>

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

      {status?.total_draws === 0 && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5 text-sm text-zinc-600 space-y-2">
          <p className="font-medium text-zinc-800">Como carregar o histórico</p>
          <p>
            1. <strong>Sincronizar sorteios</strong> busca tudo da API da Caixa (com fallback
            automático) e guarda no cache local — só baixa o que falta.
          </p>
          <p>
            2. Se as duas APIs estiverem fora do ar, <strong>Importar CSV</strong> aceita um
            arquivo com colunas <code className="bg-zinc-100 px-1 rounded">concurso, data, dezena1..dezena6</code>{' '}
            (separado por vírgula ou ponto e vírgula, com ou sem cabeçalho).
          </p>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((d) => (
          <div key={d.concurso} className="bg-white border border-zinc-200 rounded-xl p-4">
            <div className="flex items-baseline justify-between mb-2">
              <span className="font-semibold text-sm">Concurso {d.concurso}</span>
              <span className="text-xs text-zinc-500">{formatDate(d.data)}</span>
            </div>
            <BallRow dezenas={d.dezenas} size="sm" />
          </div>
        ))}
      </div>

      {items.length < total && (
        <div className="text-center">
          <button
            onClick={loadMore}
            className="px-4 py-2 rounded-lg border border-zinc-300 bg-white text-sm font-medium hover:bg-zinc-50"
          >
            Carregar mais ({items.length} de {total})
          </button>
        </div>
      )}
    </div>
  )
}
