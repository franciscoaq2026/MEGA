import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet, apiUpload } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import { formatDate } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'
import { EVENTO_SORTEIOS, sincronizarSorteios } from '../lib/sincronizar.js'

const PAGE = 24

export default function Sorteios() {
  const { cfg } = useLottery()
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

  // A sincronização em segundo plano (ao abrir o app) avisa quando grava algo.
  useEffect(() => {
    const atualizar = () => reload().catch(() => {})
    window.addEventListener(EVENTO_SORTEIOS, atualizar)
    return () => window.removeEventListener(EVENTO_SORTEIOS, atualizar)
  }, [reload])

  async function syncAll() {
    setBusy(true)
    setMessage(null)
    try {
      const r = await sincronizarSorteios(cfg, setSync)
      const total = r.servidor + (r.direto?.enviados ?? 0)
      let texto
      if (r.direto) {
        texto =
          r.direto.enviados > 0
            ? `Sincronizado: ${total} concurso(s) novo(s) — ${r.direto.enviados} vindo(s) da ${r.direto.fonte} direto pelo seu navegador. Tudo atualizado até o concurso ${r.direto.atualRemoto}.`
            : `Sincronizado: ${total} concurso(s) novo(s). Você já está no concurso mais recente (${r.direto.atualRemoto}).`
      } else if (r.semLogin) {
        texto = `Sincronizado: ${total} concurso(s) novo(s), dos espelhos do servidor (atualizados uma vez por dia). Para trazer o resultado mais recente direto da Caixa, entre na sua conta em Meus jogos.`
      } else {
        texto = `Sincronizado: ${total} concurso(s) novo(s), dos espelhos do servidor. Não consegui consultar a Caixa pelo navegador (rede/CORS) — o resultado mais recente entra quando os espelhos forem atualizados.`
      }
      if (r.avisos.length) texto += ` Aviso: ${r.avisos[0]}.`
      // O laço do servidor parou sem gravar nada: ainda faltam concursos que
      // nenhuma fonte entregou. Avisar é melhor do que ficar repetindo o mesmo
      // pedido — e o CSV continua sendo a saída.
      setMessage(
        r.travou
          ? {
              type: 'error',
              text: `${texto} Ainda faltam concursos que nenhuma fonte entregou — tente de novo mais tarde ou importe um CSV abaixo.`,
            }
          : { type: 'ok', text: texto },
      )
      await reload()
    } catch (e) {
      setMessage({
        type: 'error',
        text: `${e.message} — se as fontes estiverem fora do ar, use a importação de CSV abaixo.`,
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
            1. <strong>Sincronizar sorteios</strong> carrega o histórico embutido no app e os
            espelhos públicos no GitHub (atualizados todo dia a partir da Caixa) e, se você
            estiver logado, busca direto na Caixa, pelo seu navegador, o resultado mais recente.
            Só baixa o que falta — e o app faz isso sozinho quando é aberto.
          </p>
          <p>
            2. Se as fontes estiverem fora do ar, <strong>Importar CSV</strong> (precisa estar
            logado) aceita um arquivo com colunas{' '}
            <code className="bg-zinc-100 px-1 rounded">
              concurso, data, dezena1..dezena{cfg.sorteadas}
            </code>{' '}
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
