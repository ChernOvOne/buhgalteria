import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { clsx } from '@/utils'
import {
  LayoutDashboard, TrendingUp, TrendingDown, Megaphone,
  Server, Users, ArrowLeftRight, FileText, Settings,
  LogOut, ChevronLeft, ChevronRight, Bell,
} from 'lucide-react'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Дашборд'  },
  { to: '/income',      icon: TrendingUp,      label: 'Доходы'   },
  { to: '/expenses',    icon: TrendingDown,    label: 'Расходы'  },
  { to: '/ads',         icon: Megaphone,       label: 'Реклама'  },
  { to: '/servers',     icon: Server,          label: 'Сервера'  },
  { to: '/partners',    icon: Users,           label: 'Партнёры' },
  { to: '/inkas',       icon: ArrowLeftRight,  label: 'Инкас'    },
  { to: '/reports',     icon: FileText,        label: 'Отчёты'   },
]

export function Shell({ children }) {
  const { user, logout, isAdmin } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Sidebar */}
      <aside className="w-14 flex flex-col border-r border-gray-100 bg-white flex-shrink-0">
        {/* Logo */}
        <div className="h-14 flex items-center justify-center border-b border-gray-100">
          <span className="text-lg font-semibold text-primary-600">B</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col gap-1 p-2 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
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
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-2 flex flex-col gap-1 border-t border-gray-100">
          {isAdmin() && (
            <NavLink
              to="/settings"
              title="Настройки"
              className={({ isActive }) =>
                clsx(
                  'w-10 h-10 flex items-center justify-center rounded-xl transition-all duration-150',
                  isActive
                    ? 'bg-primary-50 text-primary-600'
                    : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
                )
              }
            >
              <Settings size={18} />
            </NavLink>
          )}
          <button
            onClick={handleLogout}
            title="Выйти"
            className="w-10 h-10 flex items-center justify-center rounded-xl text-gray-400 hover:text-danger-600 hover:bg-danger-50 transition-all duration-150"
          >
            <LogOut size={18} />
          </button>
          {/* User avatar */}
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium cursor-default"
            style={{ background: (user?.avatar_color || '#534AB7') + '22', color: user?.avatar_color || '#534AB7' }}
            title={user?.full_name || user?.username}
          >
            {(user?.full_name || user?.username || '?')[0].toUpperCase()}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-100">
      <div>
        <h1 className="text-base font-medium">{title}</h1>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  )
}
