import { CloudOff, Eye, EyeOff, LogOut, Plus, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { ApiProblem, nativeAuth, type NativeAccount } from '../api'
import { useAccounts } from '../AccountContext'
import { accountDisplay, useEmailPrivacy } from '../accountPrivacy'
import { clearCachedSave } from '../accountCache'
import { distributionLabel, platformLabel } from '../accountMessages'
import { SimpleTopbar } from '../Brand'
import { Loading, PageTitle, Problem } from '../ui'

function accountTags(account: NativeAccount) {
  const platform = platformLabel(account.account?.platform) || 'Android'
  const distribution = distributionLabel(account.account?.distribution_label ?? '').replace(/^Android\s+/i, '')
  return [platform, distribution || 'Global'].filter(Boolean)
}

function AccountCard({ account, index, total }: { account: NativeAccount; index: number; total: number }) {
  const [hideEmail] = useEmailPrivacy()
  const [pending, setPending] = useState(false)
  const [problem, setProblem] = useState<ApiProblem | null>(null)
  const { reload } = useAccounts()
  const display = accountDisplay(account, { index, total, hideEmail })
  const tags = accountTags(account)

  async function unlink() {
    if (!window.confirm('¿Desvincular esta cuenta de este navegador? No se eliminarán sus respaldos ni su perfil.')) return
    const controller = new AbortController()
    setPending(true)
    setProblem(null)
    try {
      await nativeAuth.logoutAccount(account.id, controller.signal)
      clearCachedSave(account.id)
      await reload()
    } catch (error) {
      setProblem(error instanceof ApiProblem ? error : new ApiProblem('No se pudo desvincular la cuenta.'))
    } finally {
      setPending(false)
    }
  }

  return <article className="account-card" aria-label={display.label}>
    <Link className="account-card-main" to={`/cuentas/${account.id}/partida`}
      aria-label={`Abrir partida de ${display.label}`}>
      <span className="account-card-icon"><UserRound size={22} aria-hidden="true" /></span>
      <span className="account-card-copy">
        <strong title={display.title}>{display.label}</strong>
        <span className="account-tags">
          {tags.map((tag) => <span key={tag} className="account-tag">{tag}</span>)}
          {account.expired && <span className="account-tag expired"><CloudOff size={13} aria-hidden="true" />Sesión caducada</span>}
        </span>
      </span>
    </Link>
    <button className="button quiet account-unlink" type="button" disabled={pending}
      aria-label={`Desvincular ${display.label}`} aria-busy={pending} title="Desvincular cuenta" onClick={unlink}>
      <LogOut size={17} aria-hidden="true" />
    </button>
    {problem && <div className="account-card-problem"><Problem problem={problem} /></div>}
  </article>
}

export function DashboardPage() {
  const { accounts, loading, problem, reload } = useAccounts()
  const [hideEmail, setHideEmail] = useEmailPrivacy()

  return <>
    <SimpleTopbar>
      <button className="button quiet topbar-utility" type="button"
        aria-label={hideEmail ? 'Mostrar correos' : 'Ocultar correos'} aria-pressed={hideEmail}
        title={hideEmail ? 'Mostrar correos' : 'Ocultar correos'}
        onClick={() => setHideEmail((value) => !value)}>
        {hideEmail ? <Eye size={18} aria-hidden="true" /> : <EyeOff size={18} aria-hidden="true" />}
      </button>
    </SimpleTopbar>
    <main id="content" className="shell main-content dashboard">
      <PageTitle title="Dashboard" />
      {loading && accounts.length === 0 ? <Loading>Cargando cuentas…</Loading> : <>
        {problem && <Problem problem={problem} />}
        {problem && <button className="button quiet dashboard-retry" type="button" onClick={() => void reload()}>
          Reintentar
        </button>}
        <section className="account-grid" aria-label="Cuentas">
          {accounts.map((account, index) =>
            <AccountCard key={account.id} account={account} index={index} total={accounts.length} />)}
          <Link className="account-card account-card-add" to="/cuentas/nueva">
            <span className="account-add-icon"><Plus size={28} aria-hidden="true" /></span>
            <strong>Añadir cuenta</strong>
          </Link>
        </section>
      </>}
    </main>
  </>
}