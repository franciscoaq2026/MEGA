import { useState } from 'react'

// "?" clicável que abre uma explicação. Usa clique (não hover) para funcionar
// no celular; um fundo invisível fecha ao tocar fora.
export default function Help({ text, label = 'O que é isto?' }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setOpen((o) => !o)
        }}
        className={`w-4 h-4 shrink-0 rounded-full text-[10px] font-bold leading-none flex items-center justify-center transition-colors ${
          open ? 'bg-emerald-600 text-white' : 'bg-zinc-200 text-zinc-600 hover:bg-emerald-100 hover:text-emerald-700'
        }`}
      >
        ?
      </button>
      {open && (
        <>
          <span
            className="fixed inset-0 z-20"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setOpen(false)
            }}
          />
          <span
            className="absolute z-30 top-6 left-0 w-56 max-w-[calc(100vw-3rem)] bg-white border border-zinc-200 rounded-lg shadow-lg p-2.5 text-xs font-normal normal-case text-zinc-600 leading-snug break-words"
            onClick={(e) => e.stopPropagation()}
          >
            {text}
          </span>
        </>
      )}
    </span>
  )
}
