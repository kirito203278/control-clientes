import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { NotificacionesResp, Notificacion, Recordatorio } from '../api/types'
import { fechaHora, hoyIso } from '../util'
import { BotonCopiar, Modal } from './ui'

const POLL_MS = 45_000

export default function NotificationBell({ onAbrirPaquete }: { onAbrirPaquete?: (clienteId: number, paqueteId: number | null) => void }) {
  const [data, setData] = useState<NotificacionesResp | null>(null)
  const [open, setOpen] = useState(false)
  const [respondiendo, setRespondiendo] = useState<Notificacion | null>(null)
  const [recordatorio, setRecordatorio] = useState<Recordatorio | null>(null)
  const vistas = useRef<Set<number> | null>(null)       // primera carga: no spamear con lo que ya estaba
  const contenedor = useRef<HTMLDivElement>(null)

  const cargar = useCallback(async () => {
    const resp = await api.get<NotificacionesResp>('/notificaciones')
    setData(resp)
    // Notificaciones nativas del navegador solo para lo NUEVO no leído
    if (vistas.current === null) vistas.current = new Set(resp.items.map((n) => n.id))
    else for (const n of resp.items) {
      if (!n.leida && !vistas.current.has(n.id)) {
        vistas.current.add(n.id)
        if ('Notification' in window && Notification.permission === 'granted') new Notification('INNquietus', { body: n.mensaje, tag: `n-${n.id}` })
      }
    }
  }, [])

  useEffect(() => {
    cargar().catch(() => undefined)
    const t = setInterval(() => cargar().catch(() => undefined), POLL_MS)
    return () => clearInterval(t)
  }, [cargar])

  useEffect(() => {
    if (!open) return
    const fuera = (e: MouseEvent) => { if (contenedor.current && !contenedor.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [open])

  function alAbrir() {
    setOpen((o) => !o)
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission().catch(() => undefined)
  }

  async function leer(n: Notificacion) {
    if (!n.leida && !n.requiere_respuesta) { await api.post(`/notificaciones/${n.id}/leer`); cargar() }
    if (n.cliente_id && onAbrirPaquete) { setOpen(false); onAbrirPaquete(n.cliente_id, n.paquete_id) }
  }

  const conteo = data?.no_leidas ?? 0
  return (
    <div style={{ position: 'relative' }} ref={contenedor}>
      <button className="btn btn-ghost-dark btn-sm" style={{ position: 'relative' }} onClick={alAbrir} title="Notificaciones" aria-label="Notificaciones">
        🔔
        {conteo > 0 && <span style={{ position: 'absolute', top: -2, right: -2, background: 'var(--inn-orange)', color: 'white', borderRadius: 999,
          fontSize: 10, fontWeight: 700, minWidth: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px' }}>{conteo}</span>}
      </button>

      {open && (
        <div className="card" style={{ position: 'absolute', top: 34, left: 0, width: 340, maxHeight: 440, overflowY: 'auto', zIndex: 50, padding: 10, color: 'var(--ink-900)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <strong style={{ fontSize: 13 }}>Notificaciones</strong>
            {conteo > 0 && <button className="btn btn-ghost btn-sm" onClick={async () => { await api.post('/notificaciones/leer-todas'); cargar() }}>Marcar leídas</button>}
          </div>
          {!data?.items.length && <p className="muted" style={{ fontSize: 13, margin: 0 }}>Sin notificaciones.</p>}
          {data?.items.map((n) => (
            <div key={n.id} style={{ padding: '8px 10px', borderRadius: 8, fontSize: 13, marginBottom: 4, cursor: 'pointer',
              background: n.leida ? 'transparent' : 'var(--inn-purple-50)', border: n.requiere_respuesta && !n.respondida_en ? '1px solid var(--inn-orange)' : '1px solid transparent' }}
              onClick={() => leer(n)}>
              <div>{n.mensaje}</div>
              <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>{fechaHora(n.creado_en)}</div>
              {n.requiere_respuesta && !n.respondida_en && (
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }} onClick={(e) => e.stopPropagation()}>
                  <button className="btn btn-primary btn-sm" onClick={() => setRespondiendo(n)}>Sí pagó</button>
                  <button className="btn btn-secondary btn-sm" onClick={async () => {
                    const r = await api.post<{ recordatorio: Recordatorio }>(`/notificaciones/${n.id}/responder`, { pago: 'no' })
                    setRecordatorio(r.recordatorio); cargar()
                  }}>No pagó</button>
                </div>
              )}
              {n.respuesta && <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>Respondida: {n.respuesta === 'si' ? 'sí pagó' : 'no pagó'}</div>}
            </div>
          ))}
        </div>
      )}

      {respondiendo && <PagoDeNotificacion n={respondiendo} onClose={() => setRespondiendo(null)} onHecho={() => { setRespondiendo(null); cargar() }} />}
      {recordatorio && <RecordatorioModal r={recordatorio} onClose={() => setRecordatorio(null)} />}
    </div>
  )
}

function PagoDeNotificacion({ n, onClose, onHecho }: { n: Notificacion; onClose: () => void; onHecho: () => void }) {
  const [monto, setMonto] = useState('')
  const [fecha, setFecha] = useState(hoyIso())
  const [error, setError] = useState<string | null>(null)
  async function enviar() {
    setError(null)
    try { await api.post(`/notificaciones/${n.id}/responder`, { pago: 'si', monto: Number(monto), fecha }); onHecho() }
    catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo registrar el pago') }
  }
  return (
    <Modal title="Capturar pago del cliente" onClose={onClose} width={440}>
      <p className="muted" style={{ marginTop: 0 }}>{n.mensaje}</p>
      <div className="field"><label>Monto pagado</label><input type="number" min="0" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} autoFocus /></div>
      <div className="field"><label>Fecha del pago</label><input type="date" max={hoyIso()} value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
      {error && <p className="error-text">{error}</p>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" disabled={!Number(monto)} onClick={enviar}>Registrar pago</button>
      </div>
    </Modal>
  )
}

export function RecordatorioModal({ r, onClose, onEnviado }: { r: Recordatorio; onClose: () => void; onEnviado?: () => void }) {
  const [enviado, setEnviado] = useState(!!r.enviado_en)
  async function marcar() { await api.post(`/recordatorios/${r.id}/marcar-enviado`); setEnviado(true); onEnviado?.() }
  return (
    <Modal title="Recordatorio para el cliente" onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>Mensaje ya redactado. Ábrelo en WhatsApp o cópialo, y marca cuándo lo enviaste.</p>
      <textarea readOnly rows={6} value={r.texto} />
      {!r.wa_url && <div className="callout callout-warn">El cliente no tiene un teléfono válido guardado: puedes copiar el texto, pero no abrir WhatsApp.</div>}
      <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
        {r.wa_url && <a className="btn btn-primary" href={r.wa_url} target="_blank" rel="noreferrer">Abrir en WhatsApp</a>}
        <BotonCopiar texto={r.texto} />
        <button className="btn btn-secondary right" disabled={enviado} onClick={marcar}>{enviado ? '✓ Marcado como enviado' : 'Marcar como enviado'}</button>
      </div>
    </Modal>
  )
}
