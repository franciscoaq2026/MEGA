import { createContext, useContext } from 'react'
import { getLoteria } from './lotteries.js'

const LotteryContext = createContext(null)

export function LotteryProvider({ code, children }) {
  const cfg = getLoteria(code)
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
