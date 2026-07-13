import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Sorteios from './pages/Sorteios.jsx'
import GerarJogos from './pages/GerarJogos.jsx'
import MeusJogos from './pages/MeusJogos.jsx'

// Estatísticas carrega o Recharts (pesado) — só baixa ao abrir a página
const Estatisticas = lazy(() => import('./pages/Estatisticas.jsx'))

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="sorteios" element={<Sorteios />} />
        <Route
          path="estatisticas"
          element={
            <Suspense
              fallback={<p className="text-sm text-zinc-500">Carregando estatísticas…</p>}
            >
              <Estatisticas />
            </Suspense>
          }
        />
        <Route path="gerar" element={<GerarJogos />} />
        <Route path="meus-jogos" element={<MeusJogos />} />
      </Route>
    </Routes>
  )
}
