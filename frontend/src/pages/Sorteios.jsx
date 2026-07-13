import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet, apiPost, apiUpload } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import { formatDate } from '../lib/format.js'

const PAGE = 24

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
      for (;;) {
        const r = await apiPost('/sync')
        added += r.added
        setSync({ added, remaining: r.remaining })
        if (r.remaining <= 0) break
      }
      setMessage({ type: 'ok', text: `Sincronizado: ${added} concurso(s) novo(s).` })
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
            {sync ? `Sincronizando… ${sync.added} baixados, faltam ${sync.remaining}` : 'Sincronizar sorteios'}
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
