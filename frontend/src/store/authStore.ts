import { create } from 'zustand'

interface AuthUser {
  id: number
  username: string
  token: string
}

interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  login: (user: AuthUser) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => {
  // Restaurer depuis localStorage
  const stored = localStorage.getItem('user')
  const initial = stored ? JSON.parse(stored) : null

  return {
    user: initial,
    isAuthenticated: !!initial,

    login: (user) => {
      localStorage.setItem('token', user.token)
      localStorage.setItem('user', JSON.stringify(user))
      set({ user, isAuthenticated: true })
    },

    logout: () => {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      set({ user: null, isAuthenticated: false })
    },
  }
})
