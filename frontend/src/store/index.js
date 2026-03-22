import { create } from 'zustand'
import { authAPI } from '@/api'

export const useAuthStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: true,

  login: async (username, password) => {
    const res = await authAPI.login({ username, password })
    const { access_token, user } = res.data
    localStorage.setItem('token', access_token)
    set({ token: access_token, user })
    return user
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null })
  },

  fetchMe: async () => {
    try {
      const res = await authAPI.me()
      set({ user: res.data, loading: false })
    } catch {
      set({ user: null, token: null, loading: false })
      localStorage.removeItem('token')
    }
  },

  isAdmin: () => get().user?.role === 'admin',
  isEditor: () => ['admin', 'editor'].includes(get().user?.role),
}))

export const useUIStore = create((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  activeModal: null,
  modalData: null,
  openModal: (name, data = null) => set({ activeModal: name, modalData: data }),
  closeModal: () => set({ activeModal: null, modalData: null }),
}))
