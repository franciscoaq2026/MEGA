import { NavLink, Outlet, useParams, Navigate } from 'react-router-dom'
import Disclaimer from './Disclaimer.jsx'
import { isValidLoteria } from '../lib/lotteries.js'
import { LotteryProvider, useLottery } from '../lib/LotteryContext.jsx'

const PAGES = [
  { sub: '', label: 'Início', end: true },
  { sub: 'sorteios', label: 'Sorteios' },
  { sub: 'estatisticas', label: 'Estatísticas' },
  { sub: 'gerar', label: 'Gerar jogos' },
  { sub: 'fabrica', label: 'Fábrica', onlyAvancada: true },
  { sub: 'meus-jogos', label: 'Meus jogos' },
]

function Shell() {
  const { cfg, basePath } = useLottery()
  const links = PAGES.filter((p) => !p.onlyAvancada || cfg.avancada)

  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 flex flex-col">
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center gap-3 pt-3 pb-2">
            <NavLink
              to="/"
              className="text-zinc-400 hover:text-zinc-700 text-sm shrink-0"
              title="Voltar ao início (escolher loteria)"
            >
              ←
            </NavLink>
            <div
              className={`w-9 h-9 rounded-full ${cfg.badgeClass} text-white flex items-center justify-center font-bold shrink-0`}
            >
              {cfg.badge}
            </div>
            <div className="min-w-0">
              <h1 className="font-bold leading-tight">{cfg.nome} Stats</h1>
              <p className="text-xs text-zinc-500 leading-tight truncate">
                análise estatística e geração de jogos
              </p>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto">
            {links.map(({ sub, label, end }) => (
              <NavLink
                key={sub}
                to={sub ? `${basePath}/${sub}` : basePath}
                end={end}
                className={({ isActive }) =>
                  `whitespace-nowrap px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-emerald-600 text-emerald-700'
                      : 'border-transparent text-zinc-500 hover:text-zinc-800'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>

      <Disclaimer />
      <footer className="text-center text-xs text-zinc-400 pb-4">
        Uso pessoal · dados públicos da Caixa Econômica Federal
      </footer>
    </div>
  )
}

// Lê a loteria da rota (/:loteria/...), valida e provê o contexto.
export default function Layout() {
  const { loteria } = useParams()
  if (!isValidLoteria(loteria)) return <Navigate to="/" replace />
  return (
    <LotteryProvider code={loteria}>
      <Shell />
    </LotteryProvider>
  )
}
