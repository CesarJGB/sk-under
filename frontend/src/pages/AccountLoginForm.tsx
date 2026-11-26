import { ChevronDown, Eye, EyeOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import {
  nativeAuth,
  type NativeConfig, type NativeSession,
} from '../api'
import { distributionLabel, friendly } from '../accountMessages'
import { useOperation } from '../useOperation'
import { Loading, Notice, Problem } from '../ui'

export function AccountLoginForm({
  config, onSuccess, onCancel, reauth = false,
}: {
  config: NativeConfig
  onSuccess: (session: NativeSession) => void
  onCancel: () => void
  reauth?: boolean
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [profileId, setProfileId] = useState(() => {
    if (!config.requires_profile_selection) return ''
    return config.profiles.length === 1 ? config.profiles[0].id : ''
  })
  const authOperation = useOperation()
  const available = config.available === true && config.login_available

  function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const email = String(data.get('email') ?? '').trim()
    const password = String(data.get('password') ?? '')
    const passwordField = form.elements.namedItem('password')
    if (passwordField instanceof HTMLInputElement) passwordField.value = ''
    const selected = config.requires_profile_selection
      ? String(data.get('profile_id') ?? profileId)
      : ''
    void authOperation.run(async (signal) => {
      const next = await nativeAuth.login({
        distribution: String(data.get('distribution') ?? 'android-global'),
        email,
        password,
        ...(selected ? { profile_id: selected } : {}),
      }, signal)
      if (!signal.aborted) onSuccess(next)
    })
  }

  return <section className="cloud-login panel" aria-labelledby="login-title">
    <h2 id="login-title">{reauth ? 'Renovar acceso a ChillyRoom' : 'Iniciar sesión en ChillyRoom'}</h2>
    {reauth && <p className="partida-muted">La sesión de esta cuenta caducó. Introduce de nuevo sus credenciales.</p>}
    {!available && <Notice tone="warning">El acceso aún no está habilitado. Contacta con el administrador.</Notice>}
    {config.auto_identity !== false && config.portal_enabled === false &&
      <Notice tone="warning">La recuperación del progreso anterior puede estar limitada temporalmente.</Notice>}
    <form className="cloud-form" onSubmit={login} aria-busy={authOperation.pending}>
      <label className="cloud-field"><span>Correo electrónico</span>
        <input name="email" type="email" inputMode="email" autoComplete="username" required disabled={!available} />
      </label>
      <div className="cloud-field">
        <label htmlFor="native-password">Contraseña</label>
        <span className="password-control">
          <input id="native-password" name="password" type={showPassword ? 'text' : 'password'}
            autoComplete="current-password" required disabled={!available} />
          <button className="button quiet password-toggle" type="button"
            aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            aria-pressed={showPassword} disabled={!available}
            onClick={() => setShowPassword((value) => !value)}>
            {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
          </button>
        </span>
      </div>
      <label className="cloud-field"><span>Distribución</span>
        <span className="cloud-select">
          <select name="distribution" defaultValue="android-global" disabled={!available}>
            {config.distributions.map((distribution) => <option key={distribution.id}
              value={distribution.id} disabled={!distribution.enabled}>
              {distributionLabel(distribution.label)}{distribution.enabled ? '' : ' · No disponible'}
            </option>)}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
        </span>
      </label>
      {config.requires_profile_selection && config.profiles.length > 1 &&
        <label className="cloud-field"><span>Perfil de instalación</span>
          <span className="cloud-select">
            <select name="profile_id" value={profileId} onChange={(event) => setProfileId(event.target.value)}
              disabled={!available}>
              <option value="">Selecciona un perfil</option>
              {config.profiles.map((profile) => <option key={profile.id} value={profile.id}>
                {profile.label}{profile.installation_ready ? '' : ' · Instalación pendiente'}
              </option>)}
            </select>
            <ChevronDown size={16} aria-hidden="true" />
          </span>
        </label>}
      <div className="cloud-actions login-actions">
        <button className="button primary" disabled={authOperation.pending || !available}>
          {authOperation.pending ? 'Iniciando sesión…' : reauth ? 'Renovar acceso' : 'Iniciar sesión'}
        </button>
        <button className="button quiet" type="button" disabled={authOperation.pending} onClick={onCancel}>
          Cancelar
        </button>
      </div>
      {authOperation.pending && <Loading>Conectando con ChillyRoom…</Loading>}
      {authOperation.problem && <Problem problem={friendly(authOperation.problem, 'No se pudo iniciar sesión. Vuelve a intentarlo.')} />}
    </form>
  </section>
}