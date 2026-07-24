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

        {/* Comparação de chances — as duas dimensões que decidem a escolha */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <p className="font-semibold text-sm">Comparação de chances</p>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200">
                  <th className="py-1.5 pr-3 font-medium">Loteria</th>
                  <th className="py-1.5 pr-3 font-medium">Prêmio principal</th>
                  <th className="py-1.5 pr-3 font-medium">Ganhar algo</th>
                  <th className="py-1.5 font-medium">Aposta</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-zinc-100">
                  <td className="py-2 pr-3 font-medium">Mega-Sena</td>
                  <td className="py-2 pr-3 tabular-nums">1 em 50.063.860</td>
                  <td className="py-2 pr-3 tabular-nums">1 em 2.298</td>
                  <td className="py-2 tabular-nums">R$ 6,00</td>
                </tr>
                <tr>
                  <td className="py-2 pr-3 font-medium">Lotofácil</td>
                  <td className="py-2 pr-3 tabular-nums">1 em 3.268.760</td>
                  <td className="py-2 pr-3 tabular-nums font-semibold">1 em 9</td>
                  <td className="py-2 tabular-nums">R$ 3,50</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            A Lotofácil é <strong>15× mais provável</strong> no prêmio principal e paga alguma
            coisa a cada 9 apostas — mas o prêmio é de milhões, não de dezenas de milhões. A
            Mega-Sena é o contrário: quase nunca paga, e quando paga muda a vida. Jogar uma de cada
            cobre as duas pontas. Nenhuma escolha de números altera a matemática de fundo.
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
