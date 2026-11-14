// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
import { useEffect, useState } from 'react'
import { API_BASE, getHealth, type HealthResponse, WEB_CONTRACT_VERSION } from './api/client'

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string }

export default function App() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    getHealth()
      .then((health) => setState({ kind: 'ok', health }))
      .catch((e: unknown) => setState({ kind: 'error', message: String(e) }))
  }, [])

  const mismatch =
    state.kind === 'ok' && state.health.contract_version !== WEB_CONTRACT_VERSION

  return (
    <main>
      <h1>Lunar Site Scout</h1>
      <p className="muted">Hello-world deploy check (C0).</p>
      <dl>
        <dt>API</dt>
        <dd>{API_BASE || '(same origin)'}</dd>
        <dt>API status</dt>
        <dd>
          {state.kind === 'loading' && 'checking...'}
          {state.kind === 'ok' && state.health.status}
          {state.kind === 'error' && <span className="error">unreachable: {state.message}</span>}
        </dd>
        <dt>API contract version</dt>
        <dd>{state.kind === 'ok' ? state.health.contract_version : '-'}</dd>
        <dt>Web contract version</dt>
        <dd>{WEB_CONTRACT_VERSION}</dd>
      </dl>
      {mismatch && <p className="error">Contract version mismatch between web and API.</p>}
      <footer className="muted">Not affiliated with or endorsed by NASA.</footer>
    </main>
  )
}
