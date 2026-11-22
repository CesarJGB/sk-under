import { CircleCheck, FileText, LockKeyhole, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { fieldLimits, formatSize, summarize, type Draft, type Session } from '../session'
import { NoSession, Notice, PageTitle } from '../ui'

export function EditorPage({ session, draft, update }: {
  session: Session | null
  draft: Draft
  update: (fieldId?: string, value?: string) => void
}) {
  return (
    <>
      <PageTitle title="Editar copia">Revisa los valores originales y modifica los campos habilitados.</PageTitle>
      {session ? <Fields key={session.inspection.sha256} session={session} draft={draft} update={update} /> : <NoSession />}
    </>
  )
}

function Fields({ session, draft, update }: {
  session: Session
  draft: Draft
  update: (fieldId?: string, value?: string) => void
}) {
  const { format, fields, byte_size } = session.inspection
  const categories = [...new Set(fields.map((field) => field.category))]
  const [active, setActive] = useState(categories[0])
  const { summary, invalid } = summarize(fields, draft)
  const pending = new Set([...summary.map((change) => change.field_id), ...invalid])
  const count = pending.size

  return (
    <>
      <div className="panel file-strip">
        <div className="icon-tile"><FileText size={21} aria-hidden="true" /></div>
        <div className="min-w-0">
          <strong className="wrap-anywhere">{session.name}</strong>
          <p>{format.name} · {formatSize(byte_size)}</p>
        </div>
        <span className={`edit-count ${count > 0 ? 'has-changes' : ''}`} role="status">
          {count === 1 ? '1 cambio' : `${count} cambios`}
        </span>
      </div>
      {format.compatibility === 'synthetic' && <Notice tone="warning">Estás editando datos sintéticos de demostración.</Notice>}
      {fields.length === 0 ? <Notice>El adaptador no reconoce campos que puedan mostrarse en esta copia.</Notice> : (
        <div className="workspace">
          <div className="category-nav" role="group" aria-label="Categorías de datos">
            {categories.map((category) => (
              <button className="category-button" key={category} aria-pressed={active === category}
                type="button" onClick={() => setActive(category)}>{category}</button>
            ))}
          </div>
          <section className="panel fields-panel" aria-label={active}>
            <h2>{active}</h2>
            {fields.filter((field) => field.category === active).map((field) => {
              const edited = pending.has(field.id)
              const error = invalid.has(field.id)
              const inputId = `field-${field.id}`
              return (
                <div className="field-row" key={field.id}>
                  <div className="field-title">
                    <label htmlFor={field.editable ? inputId : undefined}>{field.label}</label>
                    {edited && <span className="pending-label">Pendiente</span>}
                  </div>
                  <div className="field-values">
                    <div>
                      <span className="field-caption">Original</span>
                      <div className="original-value wrap-anywhere">{field.value}</div>
                    </div>
                    {field.editable ? (
                      <div>
                        <span className="field-caption">Valor editado</span>
                        <input id={inputId} className="input" type="text" value={draft[field.id] ?? String(field.value)}
                          inputMode={field.type === 'integer' ? 'numeric' : 'text'} autoComplete="off"
                          onChange={(event) => update(field.id, event.target.value)}
                          aria-invalid={error} aria-describedby={`${inputId}-help`} />
                        <p className={`field-help ${error ? 'invalid' : ''}`} id={`${inputId}-help`}>{fieldLimits(field)}</p>
                      </div>
                    ) : (
                      <p className="readonly"><LockKeyhole size={15} aria-hidden="true" />Solo lectura</p>
                    )}
                  </div>
                  {edited && (
                    <button className="text-button revert" type="button" onClick={() => update(field.id)}>
                      <RotateCcw size={14} />Revertir {field.label.toLowerCase()}
                    </button>
                  )}
                </div>
              )
            })}
          </section>
        </div>
      )}
      <div className="actions editor-actions">
        <button className="button quiet" type="button" disabled={!Object.keys(draft).length} onClick={() => update()}>
          <RotateCcw size={17} />Revertir todo
        </button>
        <Link className="button primary" to="/exportar"><CircleCheck size={18} />Revisar exportación</Link>
      </div>
    </>
  )
}
