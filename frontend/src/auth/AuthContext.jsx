import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, onLogout, tokens } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [email, setEmail] = useState(() => (tokens.access ? tokens.email : null))

  useEffect(() => onLogout(() => setEmail(null)), [])

  const login = useCallback(async (address, password) => {
    const { data } = await api.post('/auth/login/', { email: address, password })
    tokens.save({ access: data.access, refresh: data.refresh, email: address })
    setEmail(address)
  }, [])

  const register = useCallback(
    async (address, password) => {
      await api.post('/auth/register/', { email: address, password })
      await login(address, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    tokens.clear()
    setEmail(null)
  }, [])

  const value = useMemo(() => ({ email, login, register, logout }), [email, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
