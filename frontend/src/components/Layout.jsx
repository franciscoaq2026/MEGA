import { NavLink, Outlet } from 'react-router-dom'
import Disclaimer from './Disclaimer.jsx'

const links = [
  { to: '/', label: 'Início', end: true },
  { to: '/sorteios', label: 'Sorteios' },
  { to: '/estatisticas', label: 'Estatísticas' },
  { to: '/gerar', label: 'Gerar jogos' },
  { to: '/meus-jogos', label: 'Meus jogos' },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 flex flex-col">
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center gap-3 pt-3 pb-2">
            <div className="w-9 h-9 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold shrink-0">
              60
            </div>
            <div className="min-w-0">
              <h1 className="font-bold leading-tight">Mega-Sena Stats</h1>
              <p className="text-xs text-zinc-500 leading-tight truncate">
                análise estatística e geração de jogos
              </p>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto">
            {links.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
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
