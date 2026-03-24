import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { clsx } from '@/utils'
import {
  LayoutDashboard, TrendingUp, TrendingDown, Megaphone,
  Server, Users, ArrowLeftRight, FileText, Settings,
  LogOut, Menu, X, CreditCard, BarChart2, UserCheck,
} from 'lucide-react'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Дашборд'  },
  { to: '/income',      icon: TrendingUp,      label: 'Доходы'   },
  { to: '/expenses',    icon: TrendingDown,    label: 'Расходы'  },
  { to: '/payments',    icon: CreditCard,      label: 'Платежи'  },
  { to: '/customers',   icon: UserCheck,       label: 'Клиенты'  },
  { to: '/ads',         icon: Megaphone,       label: 'Маркетинг'},
  { to: '/servers',     icon: Server,          label: 'Сервера'  },
  { to: '/partners',    icon: Users,           label: 'Партнёры' },
  { to: '/inkas',       icon: ArrowLeftRight,  label: 'Инкас'    },
  { to: '/reports',     icon: FileText,        label: 'Отчёты'   },
  { to: '/compare',    icon: BarChart2,       label: 'Сравнение' },
]

function NavItem({ to, icon: Icon, label, onClick }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      onClick={onClick}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 text-sm',
          isActive
            ? 'bg-primary-50 text-primary-600 font-medium'
            : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
        )
      }
    >
      <Icon size={18} className="flex-shrink-0" />
      <span>{label}</span>
    </NavLink>
  )
}

function SidebarIcon({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      title={label}
      className={({ isActive }) =>
        clsx(
          'w-10 h-10 flex items-center justify-center rounded-xl transition-all duration-150',
          isActive
            ? 'bg-primary-50 text-primary-600'
            : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
        )
      }
    >
      <Icon size={18} />
    </NavLink>
  )
}

export function Shell({ children }) {
  const { user, logout, isAdmin } = useAuthStore()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface">

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-14 flex-col border-r border-gray-100 bg-white flex-shrink-0">
        <div className="h-14 flex items-center justify-center border-b border-gray-100">
          <span className="text-lg font-semibold text-primary-600">B</span>
        </div>
        <nav className="flex-1 flex flex-col gap-1 p-2 overflow-y-auto">
          {NAV.map(({ to, icon, label }) => (
            <SidebarIcon key={to} to={to} icon={icon} label={label} />
          ))}
        </nav>
        <div className="p-2 flex flex-col gap-1 border-t border-gray-100">
          {isAdmin() && <SidebarIcon to="/settings" icon={Settings} label="Настройки" />}
          <button
            onClick={handleLogout}
            title="Выйти"
            className="w-10 h-10 flex items-center justify-center rounded-xl text-gray-400 hover:text-danger-600 hover:bg-danger-50 transition-all duration-150"
          >
            <LogOut size={18} />
          </button>
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium cursor-default"
            style={{ background: (user?.avatar_color || '#534AB7') + '22', color: user?.avatar_color || '#534AB7' }}
            title={user?.full_name || user?.username}
          >
            {(user?.full_name || user?.username || '?')[0].toUpperCase()}
          </div>
        </div>
      </aside>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div className={clsx(
        'fixed top-0 left-0 h-full w-72 bg-white z-50 flex flex-col transform transition-transform duration-300 md:hidden',
        mobileOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex items-center justify-between px-4 h-14 border-b border-gray-100 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-xl flex items-center justify-center text-white font-semibold text-sm">B</div>
            <span className="font-medium text-sm">{user?.full_name || user?.username}</span>
          </div>
          <button onClick={() => setMobileOpen(false)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
            <X size={18} />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
          {NAV.map(({ to, icon, label }) => (
            <NavItem key={to} to={to} icon={icon} label={label} onClick={() => setMobileOpen(false)} />
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-gray-100 space-y-0.5">
          {isAdmin() && (
            <NavItem to="/settings" icon={Settings} label="Настройки" onClick={() => setMobileOpen(false)} />
          )}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-danger-600 hover:bg-danger-50 transition-colors"
          >
            <LogOut size={18} />
            Выйти
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Mobile topbar */}
        <div className="md:hidden flex items-center px-4 h-14 bg-white border-b border-gray-100 flex-shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 mr-3"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-medium text-primary-600">Бухгалтерия</span>
        </div>

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-center justify-between px-4 md:px-6 py-3 md:py-4 bg-white border-b border-gray-100 flex-wrap gap-2">
      <div>
        <h1 className="text-sm md:text-base font-medium">{title}</h1>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5 hidden md:block">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 flex-wrap">{children}</div>
    </div>
  )
}
