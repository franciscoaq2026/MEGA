export default function Card({ title, subtitle, children, className = '' }) {
  return (
    <section className={`bg-white border border-zinc-200 rounded-xl p-4 sm:p-5 ${className}`}>
      {title && <h3 className="font-semibold">{title}</h3>}
      {subtitle && <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>}
      <div className={title ? 'mt-3' : ''}>{children}</div>
    </section>
  )
}
