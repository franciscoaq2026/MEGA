export default function Placeholder({ title, etapa, children }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-6">
      <h2 className="text-lg font-bold mb-1">{title}</h2>
      <p className="text-sm text-zinc-500">
        Em construção — chega na etapa {etapa} do projeto.
      </p>
      {children}
    </div>
  )
}
