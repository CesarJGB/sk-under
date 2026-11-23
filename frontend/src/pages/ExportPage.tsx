import { CircleCheck, Download, FileCheck2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, type Validation } from '../api'
import { formatSize, summarize, type Draft, type Session } from '../session'
import { Loading, NoSession, Notice, PageTitle, Problem } from '../ui'
import { useOperation } from '../useOperation'

export function ExportPage({ session, draft, token }: {
  session: Session | null
  draft: Draft
  token: string
}) {
  return (
    <>
      <PageTitle title="Exportar copia">
        {session?.inspection.format.compatibility === 'read_only'
          ? 'Verifica la igualdad de los bytes y descarga una copia intacta.'
          : 'Revisa las modificaciones, valida el resultado y descarga una copia.'}
      </PageTitle>
      {session ? <ExportForm session={session} draft={draft} token={token} /> : <NoSession />}
    </>
  )
}

function ExportForm({ session, draft, token }: { session: Session; draft: Draft; token: string }) {
  const { fields, format } = session.inspection
  const readOnly = format.compatibility === 'read_only'
  const { changes, invalid, summary } = summarize(fields, draft)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [download, setDownload] = useState<{ url: string; name: string } | null>(null)
  const operation = useOperation()

  useEffect(() => () => { if (download) URL.revokeObjectURL(download.url) }, [download])

  async function validate() {
    setValidation(null)
    setDownload(null)
    const result = await operation.run((signal) => api.validate(session.content, changes, token, signal))
    if (result) setValidation(result)
  }

  async function exportCopy() {
    const result = await operation.run((signal) => api.export(session.content, changes, token, signal))
    if (!result) return
    const url = URL.createObjectURL(result.blob)
    setDownload({ url, name: result.name })
    const link = document.createElement('a')
    link.href = url
    link.download = result.name
    document.body.append(link)
    link.click()
    link.remove()
  }

  const rows = validation?.changes ?? summary
  return (
    <>
      {format.compatibility === 'synthetic' && (
        <Notice tone="warning">La copia descargada es una muestra sintética. Su compatibilidad con Soul Knight no está confirmada.</Notice>
      )}
      <section className="panel summary-panel" aria-labelledby="summary-title">
        <div className="summary-heading">
          <div className="icon-tile"><FileCheck2 size={21} aria-hidden="true" /></div>
          <div className="min-w-0">
            <h2 id="summary-title">{readOnly ? "Copia intacta" : "Resumen de modificaciones"}</h2>
            <p className="wrap-anywhere">{session.name}</p>
          </div>
        </div>
        {rows.length === 0 && invalid.size === 0 && <p className="summary-empty">{readOnly ? "La descarga conservará todos los bytes del original." : "La copia conservará todos sus valores originales."}</p>}
        {rows.length > 0 && (
          <ul className="summary-list">
            {rows.map((change) => (
              <li key={change.field_id}>
                <strong>{fields.find((field) => field.id === change.field_id)?.label ?? change.field_id}</strong>
                <div className="field-values">
                  <div><span className="field-caption">Original</span><div className="original-value wrap-anywhere">{change.original}</div></div>
                  <div><span className="field-caption">Modificado</span><div className="result-value wrap-anywhere">{change.modified}</div></div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      {invalid.size > 0 && <Notice tone="warning">Corrige los campos pendientes que no cumplen los rangos indicados.</Notice>}
      {operation.problem && <Problem problem={operation.problem} fields={fields} />}
      {operation.pending && <Loading>{validation ? 'Preparando la descarga…' : 'Validando la copia…'}</Loading>}
      {validation && (
        <p className="success" role="status">
          <CircleCheck size={20} aria-hidden="true" />Copia verificada por el motor · {formatSize(validation.output_byte_size)}
        </p>
      )}
      <div className="actions editor-actions">
        <Link className="button quiet" to="/editor">{readOnly ? "Volver a la inspección" : "Volver al editor"}</Link>
        {validation ? (
          <button className="button primary" type="button" onClick={exportCopy} disabled={operation.pending}>
            <Download size={18} />Descargar copia
          </button>
        ) : (
          <button className="button primary" type="button" onClick={validate} disabled={operation.pending || invalid.size > 0}>
            <CircleCheck size={18} />Validar copia
          </button>
        )}
      </div>
      {download && (
        <p className="privacy-note" role="status">Copia preparada. <a href={download.url} download={download.name} className="text-button">Descargar de nuevo</a></p>
      )}
    </>
  )
}
