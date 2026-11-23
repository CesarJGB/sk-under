import { AlertTriangle, FileUp, Info, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { ApiProblem, EditorField } from './api'

export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-title">
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  )
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' }) {
  const Icon = tone === 'warning' ? AlertTriangle : Info
  return <div className={`notice notice-${tone}`}><Icon aria-hidden="true" size={19} /><div>{children}</div></div>
}

export function Problem({ problem, fields = [] }: { problem: ApiProblem; fields?: EditorField[] }) {
  return (
    <div className="notice notice-error" role="alert">
      <AlertTriangle size={19} aria-hidden="true" />
      <div>
        <strong>{problem.message}</strong>
        {problem.issues.length > 0 && (
          <ul className="mt-2 list-disc ps-4">
            {problem.issues.map((issue, index) => {
              const label = fields.find((field) => field.id === issue.field_id)?.label
              return <li key={index}>{label && <strong>{label}. </strong>}{issue.message}</li>
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

export function Loading({ children }: { children: ReactNode }) {
  return <p className="loading" role="status"><LoaderCircle size={18} aria-hidden="true" />{children}</p>
}

export function NoSession() {
  return (
    <div className="panel empty">
      <div className="icon-tile"><FileUp size={23} aria-hidden="true" /></div>
      <h2>Importa un archivo compatible</h2>
      <p>Los campos y las opciones de exportación aparecen tras inspeccionar una copia reconocida.</p>
      <Link className="button primary" to="/importar"><FileUp size={18} />Importar archivo</Link>
    </div>
  )
}
