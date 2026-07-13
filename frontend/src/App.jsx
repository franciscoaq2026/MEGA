import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Sorteios from './pages/Sorteios.jsx'
import Estatisticas from './pages/Estatisticas.jsx'
import GerarJogos from './pages/GerarJogos.jsx'
import MeusJogos from './pages/MeusJogos.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="sorteios" element={<Sorteios />} />
        <Route path="estatisticas" element={<Estatisticas />} />
        <Route path="gerar" element={<GerarJogos />} />
        <Route path="meus-jogos" element={<MeusJogos />} />
      </Route>
    </Routes>
  )
}
