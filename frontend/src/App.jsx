import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Hub from './pages/Hub.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Sorteios from './pages/Sorteios.jsx'
import GerarJogos from './pages/GerarJogos.jsx'
import Probabilidades from './pages/Probabilidades.jsx'
import Comparar from './pages/Comparar.jsx'
import Fabrica from './pages/Fabrica.jsx'
import MeusJogos from './pages/MeusJogos.jsx'

// Estatísticas carrega o Recharts (pesado) — só baixa ao abrir a página
const Estatisticas = lazy(() => import('./pages/Estatisticas.jsx'))

export default function App() {
  return (
    <Routes>
      {/* Hub: escolha da loteria */}
      <Route index element={<Hub />} />

      {/* Comparativo das 11 modalidades da Caixa — vive acima das loterias,
          porque fala de todas, inclusive as que o app não opera. */}
      <Route path="comparar" element={<Comparar />} />

      {/* Cada loteria vive sob /:loteria (ex.: /mega, /lofa) */}
      <Route path=":loteria" element={<Layout />}>
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
        <Route path="probabilidades" element={<Probabilidades />} />
        <Route path="gerar" element={<GerarJogos />} />
        <Route path="fabrica" element={<Fabrica />} />
        <Route path="meus-jogos" element={<MeusJogos />} />
      </Route>
    </Routes>
  )
}
