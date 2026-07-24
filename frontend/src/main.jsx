import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// HashRouter dispensa configuração de rewrites no servidor — as rotas do app
// (ex.: /#/estatisticas) funcionam em qualquer hospedagem estática (Vercel etc.)
import { HashRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'
import { consumeLoginTokenFromUrl } from './lib/auth.js'
import { limparLoteriasRemovidas } from './lib/bets.js'

// Apaga do navegador os jogos de loterias que saíram do app. Roda uma vez só.
limparLoteriasRemovidas()

function render() {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <HashRouter>
        <App />
      </HashRouter>
    </StrictMode>,
  )
}

// Se o usuário chegou pelo link de acesso do e-mail (?login_token=...),
// conclui o login antes de montar o app para a sessão já valer na 1ª tela.
consumeLoginTokenFromUrl().finally(render)
