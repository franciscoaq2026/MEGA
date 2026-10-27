import { useLottery } from '../lib/LotteryContext.jsx'

export default function Disclaimer() {
  const { cfg } = useLottery()
  return (
    <div className="w-full max-w-6xl mx-auto px-4 pb-2">
      <p className="text-xs text-zinc-500 bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2">
        <span className="font-semibold text-zinc-600">Aviso:</span> cada sorteio da{' '}
        {cfg.nome} é independente — nenhuma estratégia aumenta a chance de acerto de um
        jeito que faça diferença no bolso: no histórico real, a melhor ganhou do acaso por
        centésimos de acerto por jogo. A única coisa que muda a probabilidade de verdade é
        jogar mais dezenas ou mais bilhetes, pagando proporcionalmente por isso. As
        estatísticas deste app servem como exploração de dados e entretenimento, não
        como previsão.
      </p>
    </div>
  )
}
