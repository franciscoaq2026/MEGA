import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../lib/api.js'
import { BallRow } from '../components/Ball.jsx'
import { formatDate, formatMoney } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'

export default function Dashboard() {
  const { code } = useLottery()
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/status')
      .then(setStatus)
      .catch((e) => setError(e.message))
  }, [])

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
            Vá em <strong>Sorteios</strong> e clique em “Sincronizar sorteios” — o app baixa o
            histórico completo da Caixa e guarda em cache local.
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
            {status.proximo ? (
              <div className="mt-2 space-y-1">
                <p className="font-semibold">
                  {status.proximo.concurso ? `Nº ${status.proximo.concurso}` : '—'}
                  {status.proximo.data ? ` · ${formatDate(status.proximo.data)}` : ''}
                </p>
                <p className="text-sm text-zinc-600">
                  Prêmio estimado:{' '}
                  <span className="font-semibold text-emerald-700">
                    {formatMoney(status.proximo.estimativa)}
                  </span>
                  {status.proximo.acumulado ? ' (acumulado)' : ''}
                </p>
                {/* A data vem do payload do concurso anterior. Quando a Caixa
                    remarca um sorteio, o portal muda mas a API não — conferido
                    em 25/07/2026: a API dizia 25/07 para o concurso 3745 da
                    Lotofácil enquanto o portal marcava domingo 26/07. Por isso
                    o link de conferência aparece SEMPRE, não só quando vence. */}
                {!status.proximo.data && status.proximo.estimativa != null ? (
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1.5">
                    {status.proximo.data_vencida
                      ? 'A data que a Caixa informou já passou — o sorteio deve ter sido remarcado. '
                      : 'A Caixa ainda não publicou a data deste concurso. '}
                    <a
                      href="https://loterias.caixa.gov.br/Paginas/default.aspx"
                      target="_blank"
                      rel="noreferrer"
                      className="underline font-medium"
                    >
                      Conferir no site da Caixa
                    </a>
                  </p>
                ) : (
                  status.proximo.data && (
                    <p className="text-[11px] text-zinc-400">
                      data conforme a API da Caixa — sorteios podem ser remarcados,{' '}
                      <a
                        href="https://loterias.caixa.gov.br/Paginas/default.aspx"
                        target="_blank"
                        rel="noreferrer"
                        className="underline hover:text-zinc-600"
                      >
                        confira no portal
                      </a>
                    </p>
                  )
                )}
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
