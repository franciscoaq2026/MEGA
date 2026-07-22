import { createContext, useContext } from 'react'
import { getLoteria } from './lotteries.js'
import { setApiLoteria } from './api.js'

const LotteryContext = createContext(null)

export function LotteryProvider({ code, children }) {
  const cfg = getLoteria(code)
  // Definido de forma SÍNCRONA no render (antes dos efeitos dos filhos), para
  // que toda chamada de API das páginas já use a loteria correta — um efeito
  // aqui rodaria depois dos efeitos das páginas (filhos correm antes do pai).
  setApiLoteria(cfg.code)
  const value = {
    code: cfg.code,
    cfg,
    basePath: `/${cfg.code}`, // prefixo das rotas desta loteria (HashRouter)
    // Monta um caminho interno relativo à loteria atual: path('gerar') -> /mega/gerar
    path: (sub = '') => `/${cfg.code}${sub ? `/${sub.replace(/^\//, '')}` : ''}`,
  }
  return <LotteryContext.Provider value={value}>{children}</LotteryContext.Provider>
}

export function useLottery() {
  const v = useContext(LotteryContext)
  if (!v) throw new Error('useLottery deve ser usado dentro de <LotteryProvider>')
  return v
}
