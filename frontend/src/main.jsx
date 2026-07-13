import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// HashRouter dispensa configuração de rewrites no servidor — as rotas do app
// (ex.: /#/estatisticas) funcionam em qualquer hospedagem estática (Vercel etc.)
import { HashRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
)
