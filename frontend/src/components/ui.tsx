import { useEffect, useState, type ReactNode } from 'react'
import type { Semaforo as SemaforoT } from '../api/types'
import { SEMAFORO_LABEL } from '../util'

export function Modal({ title, onClose, children, width }: { title: string; onClose?: () => void; children: ReactNode; width?: number }) {
  // Los modales NO se cierran al hacer clic afuera (decisión heredada del proyecto anterior): solo con sus botones.
  return (
    <div className="modal-backdrop">
      <div className="modal" style={width ? { maxWidth: width } : undefined} role="dialog" aria-modal="true" aria-label={title}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
          {onClose && <button className="btn btn-ghost btn-sm right" onClick={onClose} aria-label="Cerrar">✕</button>}
        </div>
        {children}
      </div>
    </div>
  )
}

export function Semaforo({ valor, conTexto }: { valor: SemaforoT | null; conTexto?: boolean }) {
  if (!valor) return null
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} title={SEMAFORO_LABEL[valor]}>
      <span className={`semaforo-dot sem-${valor}`} />
      {conTexto && <span style={{ fontSize: 13 }}>{SEMAFORO_LABEL[valor]}</span>}
    </span>
  )
}

export function Progreso({ pct }: { pct: number }) {
  return <div className="progress" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${Math.min(100, pct)}%` }} /></div>
}

export function Spinner() {
  return <span className="spinner" style={{ borderTopColor: 'var(--inn-purple-600)', borderColor: 'var(--inn-purple-100)', display: 'inline-block' }} />
}

export function Cargando() {
  return <div style={{ padding: 40, textAlign: 'center' }}><Spinner /></div>
}

export function ErrorTexto({ texto }: { texto: string | null }) {
  return texto ? <p className="error-text">{texto}</p> : null
}

export function useToast(): [ReactNode, (t: string) => void] {
  const [texto, setTexto] = useState<string | null>(null)
  useEffect(() => {
    if (!texto) return
    const t = setTimeout(() => setTexto(null), 3500)
    return () => clearTimeout(t)
  }, [texto])
  return [texto ? <div className="toast" role="status">{texto}</div> : null, setTexto]
}

export async function copiar(texto: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(texto); return true } catch {
    const ta = document.createElement('textarea')
    ta.value = texto; document.body.appendChild(ta); ta.select()
    const ok = document.execCommand('copy'); ta.remove(); return ok
  }
}

export function BotonCopiar({ texto, etiqueta = 'Copiar' }: { texto: string; etiqueta?: string }) {
  const [ok, setOk] = useState(false)
  return <button className="btn btn-secondary btn-sm" onClick={async () => { setOk(await copiar(texto)); setTimeout(() => setOk(false), 1800) }}>{ok ? '✓ Copiado' : etiqueta}</button>
}

/** Modal que muestra una contraseña generada UNA sola vez. */
export function PasswordUnaVez({ titulo, username, password, onClose }: { titulo: string; username: string; password: string; onClose: () => void }) {
  return (
    <Modal title={titulo}>
      <p style={{ marginTop: 0 }}>Usuario: <strong>{username}</strong></p>
      <div className="pw-box">{password}</div>
      <div className="callout callout-warn">Esta contraseña se muestra <strong>una sola vez</strong>. Cópiala y entrégala ahora: el sistema no puede mostrarla de nuevo (solo generar otra).</div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <BotonCopiar texto={password} etiqueta="Copiar contraseña" />
        <button className="btn btn-primary" onClick={onClose}>Ya la guardé</button>
      </div>
    </Modal>
  )
}
