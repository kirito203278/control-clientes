import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Bloqueo, Paquete } from '../api/types'
import { dinero, fecha, sumarDias } from '../util'
import { NoRenovarModal, RenovarModal } from '../pages/shared/modales'
import { ErrorTexto, Modal } from './ui'

/** Ventana que "para todo": aparece al terminar el contrato (R 23:59) de un paquete sin decisión y no se puede cerrar.
 * Solo deja las salidas que permite el servidor: Renovó (si ya pagó completo) · No renovó · Solicitó prórroga (si debe). */
export default function BloqueoModal({ onResuelto }: { onResuelto: () => void }) {
  const [lista, setLista] = useState<Bloqueo[]>([])
  const [accion, setAccion] = useState<'renovar' | 'no' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = useCallback(() => api.get<Bloqueo[]>('/bloqueos').then(setLista).catch(() => undefined), [])
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 60_000)
    return () => clearInterval(t)
  }, [cargar])

  const b = lista[0]
  if (!b) return null
  const hecho = async () => { setAccion(null); await cargar(); onResuelto() }

  if (accion === 'renovar') return <RenovarModal p={b as Paquete} onClose={() => setAccion(null)} onHecho={hecho} />
  if (accion === 'no') return <NoRenovarModal p={b as Paquete} esUltimo={false} nombreCliente={b.cliente_nombre} onClose={() => setAccion(null)} onHecho={hecho} />

  async function prorroga() {
    setError(null)
    try { await api.post(`/paquetes/${b.id}/prorroga`); await hecho() } catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo activar') }
  }
  return (
    <Modal title="Terminó el contrato: decide antes de continuar" width={560}>
      <div className="callout callout-bad" style={{ marginTop: 0 }}>
        <strong>{b.cliente_nombre}</strong> · {b.paquete} ({b.tipo}) · terminó el {fecha(b.fecha_renovacion)} a las 11:59 pm.
        {lista.length > 1 && <> Tienes <strong>{lista.length}</strong> paquetes pendientes de decidir.</>}
      </div>
      <p style={{ margin: '0 0 6px' }}>{b.restante > 0 ? <>El cliente debe <strong>{dinero(b.restante)}</strong> de {dinero(b.costo)}.</> : <>El paquete está pagado por completo ({dinero(b.costo)}).</>}</p>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        Mientras no lo resuelvas, este cliente y sus paquetes quedan bloqueados.
        {b.limite_decision && <> Si no decides, el {fecha(sumarDias(b.limite_decision, 1))} pasa automáticamente a No renovados.</>}
      </p>
      <ErrorTexto texto={error} />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end', marginTop: 14 }}>
        {b.opciones_bloqueo.includes('no_renovo') && <button className="btn btn-secondary" onClick={() => setAccion('no')}>No renovó</button>}
        {b.opciones_bloqueo.includes('prorroga') && <button className="btn btn-secondary" onClick={prorroga}>Solicitó prórroga (5 días)</button>}
        {b.opciones_bloqueo.includes('renovo') && <button className="btn btn-primary" onClick={() => setAccion('renovar')}>Renovó</button>}
      </div>
      {b.opciones_bloqueo.includes('prorroga') && <p className="muted" style={{ fontSize: 12, margin: '10px 0 0' }}>
        La prórroga dura 5 días naturales desde hoy (la fecha es automática). En ese plazo puedes registrar el pago parcial o el resto; si no se completa, el cliente pasa solo a No renovados.</p>}
    </Modal>
  )
}
