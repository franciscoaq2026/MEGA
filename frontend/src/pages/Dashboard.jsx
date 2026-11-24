import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import { formatDate, formatMoney } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'
import { EVENTO_SORTEIOS, buscarProximoDireto } from '../lib/sincronizar.js'

export default function Dashboard() {
  const { code, cfg } = useLottery()
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [proximoDireto, setProximoDireto] = useState(null)

  useEffect(() => {
    const carregar = () =>
      apiGet('/status')
        .then(setStatus)
        .catch((e) => setError(e.message))
    carregar()
    // a sincronização em segundo plano avisa quando grava sorteio novo
    window.addEventListener(EVENTO_SORTEIOS, carregar)
    return () => window.removeEventListener(EVENTO_SORTEIOS, carregar)
  }, [])

  // O banco só tem data/prêmio do próximo concurso quando o último resultado
  // veio da Caixa pelo navegador de alguém logado. Se faltar, busca direto
  // (só para exibir, nada é gravado).
  const proximoBanco = status?.proximo
  const faltaInfo = proximoBanco && (proximoBanco.estimativa == null || !proximoBanco.data)
  useEffect(() => {
    if (!faltaInfo) return
    let vivo = true
    buscarProximoDireto(cfg, proximoBanco.concurso).then((p) => {
      if (vivo) setProximoDireto(p)
    })
    return () => {
      vivo = false
    }
  }, [faltaInfo, proximoBanco?.concurso, cfg])

  const proximo =
    faltaInfo && proximoDireto
      ? {
          ...proximoBanco,
          ...proximoDireto,
          data: proximoBanco.data || proximoDireto.data,
          estimativa: proximoBanco.estimativa ?? proximoDireto.estimativa,
        }
      : proximoBanco

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Início</h2>

      {error && (
        <div className="bg-white border border-red-200 rounded-xl p-4 text-sm">
          <p className="font-medium text-red-700">Backend fora do ar</p>
          <p className="text-zinc-500 mt-1">
            Inicie o backend com{' '}
            <code className="bg-zinc-100 px-1 rounded">uvicorn app.main:app --reload</code> na pasta{' '}
            <code className="bg-zinc-100 px-1 rounded">backend/</code>. ({error})
          </p>
        </div>
      )}

      {status && status.total_draws === 0 && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5">
          <p className="font-semibold">Bem-vindo! Comece carregando o histórico de sorteios.</p>
          <p className="text-sm text-zinc-500 mt-1">
            O app carrega o histórico sozinho em alguns segundos. Se nada aparecer, vá em{' '}
            <strong>Sorteios</strong> e clique em “Sincronizar sorteios”.
          </p>
          <Link
            to={`/${code}/sorteios`}
            className="inline-block mt-3 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
          >
            Ir para Sorteios
          </Link>
        </div>
      )}

      {status && status.total_draws > 0 && (
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <p className="text-sm text-zinc-500">
              Último sorteio · concurso {status.ultimo_local.concurso} ·{' '}
              {formatDate(status.ultimo_local.data)}
            </p>
            <div className="mt-3">
              <BallRow dezenas={status.ultimo_local.dezenas} />
            </div>
          </div>
          <div className="bg-white border border-zinc-200 rounded-xl p-5">
            <p className="text-sm text-zinc-500">Próximo concurso</p>
            {proximo ? (
              <div className="mt-2 space-y-1">
                <p className="font-semibold">
                  {proximo.concurso ? `Nº ${proximo.concurso}` : '—'}
                  {proximo.data ? ` · ${formatDate(proximo.data)}` : ''}
                </p>
                <p className="text-sm text-zinc-600">
                  Prêmio estimado:{' '}
                  <span className="font-semibold text-emerald-700">
                    {formatMoney(proximo.estimativa)}
                  </span>
                  {proximo.acumulado ? ' (acumulado)' : ''}
                </p>
              </div>
            ) : (
              <p className="text-sm text-zinc-500 mt-2">
                Sincronize os sorteios para ver a data e o prêmio estimado.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-4">
        {[
          ['estatisticas', 'Estatísticas', 'Frequência, atraso, pares/ímpares, soma e gráficos'],
          ['gerar', 'Gerar jogos', 'Estratégias baseadas no histórico + probabilidades reais'],
          ['meus-jogos', 'Meus jogos', 'Seu jogo manual vs jogo do app, com conferência'],
        ].map(([to, title, desc]) => (
          <Link
            key={to}
            to={`/${code}/${to}`}
            className="bg-white border border-zinc-200 rounded-xl p-4 hover:border-emerald-400 transition-colors"
          >
            <p className="font-semibold text-sm">{title}</p>
            <p className="text-xs text-zinc-500 mt-1">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
