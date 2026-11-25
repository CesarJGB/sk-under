import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react'
import { ApiProblem, nativeAuth, type NativeAccount, type NativeConfig, type NativeSession } from './api'

type AccountState = {
  config: NativeConfig | null
  accounts: NativeAccount[]
  loading: boolean
  problem: ApiProblem | null
  reload: () => Promise<void>
}

const AccountContext = createContext<AccountState | null>(null)

export function normalizeAccounts(config: NativeConfig): NativeAccount[] {
  if (Array.isArray(config.accounts)) {
    return config.accounts
      .filter((account) => typeof account.id === 'string' || typeof account.account_id === 'string')
      .map((account) => ({ ...account, id: account.id || account.account_id || '' }))
  }
  if (config.session?.active) {
    const id = config.session.account_id || 'primary'
    const account: NativeAccount = { ...config.session, id }
    return [account]
  }
  return []
}

export function AccountsProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<NativeConfig | null>(null)
  const [accounts, setAccounts] = useState<NativeAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [problem, setProblem] = useState<ApiProblem | null>(null)
  const request = useRef<AbortController | null>(null)
  const revision = useRef(0)

  const reload = useCallback(async () => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    const current = ++revision.current
    setLoading(true)
    try {
      const next = await nativeAuth.config(controller.signal)
      if (controller.signal.aborted || current !== revision.current) return
      setConfig(next)
      setAccounts(normalizeAccounts(next))
      setProblem(null)
    } catch (error) {
      if (controller.signal.aborted || current !== revision.current) return
      setProblem(error instanceof ApiProblem ? error : new ApiProblem('No se pudieron cargar las cuentas.'))
    } finally {
      if (!controller.signal.aborted && current === revision.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
    return () => request.current?.abort()
  }, [reload])

  const value = useMemo(
    () => ({ config, accounts, loading, problem, reload }),
    [config, accounts, loading, problem, reload],
  )
  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>
}

export function useAccounts() {
  const context = useContext(AccountContext)
  if (!context) throw new Error('useAccounts debe usarse dentro de AccountsProvider')
  return context
}

export function accountById(accounts: NativeAccount[], id?: string) {
  return accounts.find((account) => account.id === id)
}

export function findSession(accounts: NativeAccount[], session: NativeSession | null) {
  if (!session?.active) return undefined
  const id = session.account_id
  return accounts.find((account) => account.id === id)
}