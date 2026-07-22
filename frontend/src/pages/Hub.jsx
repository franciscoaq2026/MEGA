import { Link } from 'react-router-dom'
import { LOTERIAS } from '../lib/lotteries.js'
import { getSession } from '../lib/auth.js'
import { loadBets } from '../lib/bets.js'

export default function Hub() {
  const session = getSession()
  const salvos = Object.fromEntries(
    Object.keys(LOTERIAS).map((code) => [code, loadBets(code).length]),
  )

  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 flex flex-col">
      <header className="bg-white border-b border-zinc-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="font-bold text-lg">Loterias Stats</h1>
          <p className="text-xs text-zinc-500">
            análise estatística e geração de jogos · escolha a loteria
          </p>
        </div>
      </header>

      <main className="flex-1 w-full max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div className="grid sm:grid-cols-2 gap-4">
          {Object.values(LOTERIAS).map((l) => (
            <Link
              key={l.code}
              to={`/${l.code}`}
              className={`bg-white border border-zinc-200 rounded-2xl p-6 transition-colors ${l.cardClass}`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-full ${l.badgeClass} text-white flex items-center justify-center font-bold`}
                >
                  {l.badge}
                </div>
                <div>
                  <p className="font-bold text-lg leading-tight">{l.nome}</p>
                  <p className="text-xs text-zinc-500">{l.blurb}</p>
                </div>
              </div>
              <p className="text-sm text-zinc-600 mt-4">
                Chance do prêmio principal: <span className="font-semibold">{l.chance}</span>
              </p>
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-zinc-500">
                  {salvos[l.code] > 0
                    ? `${salvos[l.code]} jogo(s) salvo(s) neste navegador`
                    : 'nenhum jogo salvo ainda'}
                </span>
                <span className="text-sm font-medium text-zinc-700">Entrar →</span>
              </div>
            </Link>
          ))}
        </div>

        {/* Comparação de chances — reforça a ideia de jogar um de cada */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <p className="font-semibold text-sm">Comparação de chances (prêmio principal)</p>
          <div className="grid sm:grid-cols-2 gap-3 mt-3">
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xs text-zinc-500">Mega-Sena</p>
              <p className="font-bold tabular-nums">1 em 50.063.860</p>
              <p className="text-xs text-zinc-500">R$ 6,00 · prêmio geralmente maior</p>
            </div>
            <div className="bg-zinc-50 rounded-lg p-3">
              <p className="text-xs text-zinc-500">Lotomania (20 ou 0 acertos)</p>
              <p className="font-bold tabular-nums">1 em 5.686.318</p>
              <p className="text-xs text-zinc-500">R$ 3,00 · ~8,8× mais provável, prêmio menor</p>
            </div>
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            Uma estratégia comum é jogar <strong>um de cada</strong>: a Lotomania dá mais chance de
            ganhar algo; a Mega-Sena guarda o prêmio gigante. Nenhuma muda a matemática de fundo —
            é só diversificação de gosto.
          </p>
        </div>

        <p className="text-xs text-zinc-500">
          {session ? (
            <>
              Conectado como <strong>{session.email}</strong> — seus jogos sincronizam entre
              aparelhos nas duas loterias.
            </>
          ) : (
            <>
              Dica: dentro de qualquer loteria, em <strong>Meus jogos</strong>, você pode entrar
              com seu e-mail para sincronizar o histórico entre aparelhos.
            </>
          )}
        </p>
      </main>

      <footer className="text-center text-xs text-zinc-400 pb-4">
        Uso pessoal · dados públicos da Caixa Econômica Federal
      </footer>
    </div>
  )
}
