import { clsx } from '@/utils'
import { X, Loader2 } from 'lucide-react'
import { Fragment } from 'react'

// ── Button ────────────────────────────────────────────────────────────────────
export function Button({ children, variant = 'default', size = 'md', loading, className, ...props }) {
  const base = 'inline-flex items-center gap-2 font-medium rounded-lg border transition-all duration-150 active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed'
  const variants = {
    default: 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50',
    primary: 'bg-primary-600 border-primary-600 text-white hover:bg-primary-800 hover:border-primary-800',
    danger:  'bg-danger-50 border-danger-100 text-danger-600 hover:bg-danger-100',
    success: 'bg-success-50 border-success-100 text-success-600 hover:bg-success-100',
    ghost:   'bg-transparent border-transparent text-gray-600 hover:bg-gray-100',
  }
  const sizes = {
    sm:  'px-3 py-1.5 text-xs',
    md:  'px-4 py-2 text-sm',
    lg:  'px-5 py-2.5 text-sm',
    icon:'p-2 text-sm',
  }
  return (
    <button className={clsx(base, variants[variant], sizes[size], className)} disabled={loading || props.disabled} {...props}>
      {loading ? <Loader2 size={14} className="animate-spin" /> : null}
      {children}
    </button>
  )
}

// ── Input ─────────────────────────────────────────────────────────────────────
export function Input({ label, error, className, ...props }) {
  return (
    <div className={clsx('flex flex-col gap-1', className)}>
      {label && <label className="text-xs font-medium text-gray-500">{label}</label>}
      <input
        className={clsx(
          'h-9 px-3 text-sm border rounded-lg bg-white placeholder-gray-400 transition-all duration-150',
          'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent',
          error ? 'border-danger-600' : 'border-gray-200'
        )}
        {...props}
      />
      {error && <span className="text-xs text-danger-600">{error}</span>}
    </div>
  )
}

// ── Select ────────────────────────────────────────────────────────────────────
export function Select({ label, error, children, className, ...props }) {
  return (
    <div className={clsx('flex flex-col gap-1', className)}>
      {label && <label className="text-xs font-medium text-gray-500">{label}</label>}
      <select
        className={clsx(
          'h-9 px-3 text-sm border rounded-lg bg-white transition-all duration-150',
          'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent',
          error ? 'border-danger-600' : 'border-gray-200'
        )}
        {...props}
      >
        {children}
      </select>
      {error && <span className="text-xs text-danger-600">{error}</span>}
    </div>
  )
}

// ── Textarea ──────────────────────────────────────────────────────────────────
export function Textarea({ label, className, ...props }) {
  return (
    <div className={clsx('flex flex-col gap-1', className)}>
      {label && <label className="text-xs font-medium text-gray-500">{label}</label>}
      <textarea
        className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white placeholder-gray-400
                   focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent
                   transition-all duration-150 resize-none"
        {...props}
      />
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, size = 'md', footer }) {
  if (!open) return null
  const sizes = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-2xl', xl: 'max-w-4xl' }
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.4)' }}
      onClick={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div className={clsx('bg-white rounded-2xl shadow-2xl w-full flex flex-col max-h-[90vh]', sizes[size])}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <h2 className="text-base font-medium">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors">
            <X size={16} />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-4">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-gray-100 flex-shrink-0 flex gap-2 justify-end bg-gray-50 rounded-b-2xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────────
export function Badge({ children, variant = 'info', className }) {
  const variants = {
    income:  'bg-success-50 text-success-600',
    expense: 'bg-danger-50 text-danger-600',
    warn:    'bg-warn-50 text-warn-600',
    info:    'bg-primary-50 text-primary-600',
    gray:    'bg-gray-100 text-gray-600',
    success: 'bg-success-50 text-success-600',
    danger:  'bg-danger-50 text-danger-600',
  }
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', variants[variant] || variants.info, className)}>
      {children}
    </span>
  )
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
export function KpiCard({ label, value, sub, subColor, className }) {
  return (
    <div className={clsx('bg-white border border-gray-100 rounded-xl p-4', className)}>
      <div className="text-xs text-gray-400 mb-1.5">{label}</div>
      <div className="text-xl font-medium leading-none mb-1">{value}</div>
      {sub && <div className={clsx('text-xs', subColor || 'text-gray-400')}>{sub}</div>}
    </div>
  )
}

// ── Table ─────────────────────────────────────────────────────────────────────
export function Table({ headers, children, className }) {
  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            {headers.map((h, i) => (
              <th key={i} className="text-left text-xs font-medium text-gray-400 px-4 py-3 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Tr({ children, onClick, className }) {
  return (
    <tr
      onClick={onClick}
      className={clsx(
        'border-b border-gray-50 transition-colors duration-100',
        onClick ? 'cursor-pointer hover:bg-gray-50' : 'hover:bg-gray-50/50',
        className
      )}
    >
      {children}
    </tr>
  )
}

export function Td({ children, className }) {
  return <td className={clsx('px-4 py-3 text-gray-700', className)}>{children}</td>
}

// ── Avatar ────────────────────────────────────────────────────────────────────
export function Avatar({ name, color = '#534AB7', size = 'md' }) {
  const initials = name
    ? name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
    : '?'
  const sizes = { sm: 'w-7 h-7 text-xs', md: 'w-9 h-9 text-sm', lg: 'w-11 h-11 text-base' }
  return (
    <div
      className={clsx('rounded-full flex items-center justify-center font-medium flex-shrink-0', sizes[size])}
      style={{ background: color + '22', color }}
    >
      {initials}
    </div>
  )
}

// ── Progress Bar ──────────────────────────────────────────────────────────────
export function ProgressBar({ value, max, color = '#534AB7', className }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className={clsx('h-1.5 bg-gray-100 rounded-full overflow-hidden', className)}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────────
export function Empty({ icon: Icon, text, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && <Icon size={36} className="text-gray-200 mb-3" />}
      <p className="text-sm text-gray-400">{text}</p>
      {action}
    </div>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }) {
  return <Loader2 size={size} className="animate-spin text-primary-600" />
}

// ── Section Header ────────────────────────────────────────────────────────────
export function SectionHeader({ title, children }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">{title}</h2>
      <div className="flex gap-2">{children}</div>
    </div>
  )
}
