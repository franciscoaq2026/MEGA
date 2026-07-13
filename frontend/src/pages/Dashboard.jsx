import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiGet('/health')
      .then(setHealth)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Início</h2>

      {health && (
        <div className="bg-white border border-zinc-200 rounded-xl p-4 flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
          <div className="text-sm">
            <p className="font-medium">Backend conectado</p>
            <p className="text-zinc-500">
              API v{health.version} · {new Date(health.server_time).toLocaleString('pt-BR')}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-white border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-red-700">Backend fora do ar</p>
            <p className="text-zinc-500">
              Inicie o backend com <code className="bg-zinc-100 px-1 rounded">uvicorn app.main:app --reload</code> na
              pasta <code className="bg-zinc-100 px-1 rounded">backend/</code>. ({error})
            </p>
          </div>
        </div>
      )}

      {!health && !error && (
        <div className="bg-white border border-zinc-200 rounded-xl p-4 text-sm text-zinc-500">
          Verificando conexão com o backend…
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-4">
        {[
          ['Sorteios', 'Histórico completo da Mega-Sena, sincronizado da Caixa (etapa 2)'],
          ['Estatísticas', 'Frequência, atraso, pares/ímpares, soma e gráficos (etapa 3)'],
          ['Gerar jogos', '4 estratégias baseadas no histórico (etapa 4)'],
        ].map(([title, desc]) => (
          <div key={title} className="bg-white border border-zinc-200 rounded-xl p-4">
            <p className="font-semibold text-sm">{title}</p>
            <p className="text-xs text-zinc-500 mt-1">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
