import { useEffect, useRef, useState } from 'react'
import { ApiProblem } from './api'

export function useOperation() {
  const active = useRef<AbortController | null>(null)
  const [pending, setPending] = useState(false)
  const [problem, setProblem] = useState<ApiProblem | null>(null)
  useEffect(() => () => active.current?.abort(), [])

  async function run<T>(task: (signal: AbortSignal) => Promise<T>): Promise<T | undefined> {
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    setPending(true)
    setProblem(null)
    try {
      const result = await task(controller.signal)
      return controller.signal.aborted ? undefined : result
    } catch (error) {
      if (!controller.signal.aborted) {
        setProblem(error instanceof ApiProblem ? error : new ApiProblem('No se pudo completar la solicitud. Revisa la conexión con la API.'))
      }
    } finally {
      if (!controller.signal.aborted) {
        active.current = null
        setPending(false)
      }
    }
  }

  return { pending, problem, run }
}
