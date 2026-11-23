import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/auth.api'
import { clearTokens, setSessionExpiredHandler } from '../api/axios'
import { getErrorMessage } from '../utils/format'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [initializing, setInitializing] = useState(true)
  const [sessionNotice, setSessionNotice] = useState('')

  const expireSession = useCallback(() => {
    setUser(null)
    setSessionNotice('Your session expired. Sign in again to continue.')
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(expireSession)
    authApi
      .refresh()
      .then(() => authApi.me())
      .then(setUser)
      .catch(() => {
        clearTokens()
      })
      .finally(() => setInitializing(false))
  }, [expireSession])

  const login = useCallback(async (credentials) => {
    const profile = await authApi.login(credentials)
    setUser(profile)
    setSessionNotice('')
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
      setSessionNotice('')
    } catch (error) {
      setSessionNotice(`You are signed out locally, but the server sign-out request failed: ${getErrorMessage(error)}`)
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo(
    () => ({ user, initializing, sessionNotice, login, logout }),
    [user, initializing, sessionNotice, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider.')
  return context
}
