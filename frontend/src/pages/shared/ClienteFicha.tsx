import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { ClienteFicha as Ficha, Paquete, PaqueteDetalle, Recordatorio } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { RecordatorioModal } from '../../components/NotificationBell'
import { Cargando, ErrorTexto, Progreso, Semaforo, copiar, useToast } from '../../components/ui'
import { ESTADO_LABEL, SEMAFORO_LABEL, dinero, diasTexto, fecha, hoyIso, sumarDias } from '../../util'
import { AgregarPaqueteModal, EditarPaqueteModal, NoRenovarModal, RenovarModal } from './modales'

const msg = (e: unknown, def: string) => (e instanceof ApiError ? e.message : def)
const BADGE_ESTADO: Record<string, string> = { activo: 'badge-neutral', por_vencer: 'badge-yellow', vencido: 'badge-bad', renovado: 'badge-good', archivado: 'badge-neutral', eliminado: 'badge-neutral' }

export default function ClienteFicha({ clienteId, paqueteInicial, onChanged, onDeleted, onVolver }: {
  clienteId: number; paqueteInicial?: number | null; onChanged: () => void; onDeleted: () => void; onVolver?: () => void
}) {
  const { puedeEscribir, user } = useAuth()
  const [ficha, setFicha] = useState<Ficha | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [paqueteId, setPaqueteId] = useState<number | null>(paqueteInicial ?? null)
  const [toast, avisar] = useToast()
  const [modal, setModal] = useState<'agregar' | null>(null)

  const cargar = useCallback(async (seleccionar?: number | null) => {
    try {
      const f = await api.get<Ficha>(`/clientes/${clienteId}`)
      setFicha(f)
      setPaqueteId((prev) => {
        const quiero = seleccionar ?? prev
        const todos = [...f.paquetes, ...f.historial]
        if (quiero && todos.some((p) => p.id === quiero)) return quiero
        return f.paquetes[0]?.id ?? f.historial[0]?.id ?? null
      })
    } catch (e) { setError(msg(e, 'No se pudo cargar el cliente')) }
  }, [clienteId])

  useEffect(() => { setFicha(null); setError(null); cargar(paqueteInicial) }, [clienteId, paqueteInicial, cargar])

  if (error) return <div className="card" style={{ padding: 24 }}><ErrorTexto texto={error} />{onVolver && <button className="btn btn-secondary" onClick={onVolver}>Volver</button>}</div>
  if (!ficha) return <Cargando />

  const recargarTodo = async (sel?: number | null) => { await cargar(sel); onChanged() }
  const enNoRenovados = ficha.estado === 'no_renovado'

  return (
    <div>
      {onVolver && <button className="btn btn-ghost btn-sm" onClick={onVolver} style={{ marginBottom: 8 }}>← Volver</button>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4, flexWrap: 'wrap' }}>
        <h1 className="page-title" style={{ margin: 0 }}>{ficha.nombre}</h1>
        {enNoRenovados && <span className="badge badge-bad">No renovado</span>}
        {puedeEscribir && !enNoRenovados && <button className="btn btn-secondary btn-sm right" onClick={() => setModal('agregar')}>+ Agregar paquete</button>}
      </div>
      {user?.rol === 'admin' && puedeEscribir && <p className="muted" style={{ margin: '0 0 8px', fontSize: 13 }}>Operas por cuenta del CM: tus acciones quedan en la bitácora.</p>}
      {enNoRenovados && <div className="callout callout-warn">Este cliente está en «No renovados» desde el {fecha(ficha.no_renovado_desde)}. Para reactivarlo usa <strong>No renovados → Reingresar</strong>.</div>}

      <DatosCliente ficha={ficha} puedeEscribir={puedeEscribir} onGuardado={(f) => { setFicha(f); onChanged(); avisar('Datos guardados') }} onEliminado={onDeleted} />

      <div className="section-title">Paquetes</div>
      <Paquetes ficha={ficha} paqueteId={paqueteId} setPaqueteId={setPaqueteId} puedeEscribir={puedeEscribir} recargar={recargarTodo}
        sinPaquetes={ficha.paquetes.length === 0} avisar={avisar} onClienteGone={onDeleted} />

      {ficha.historial.length > 0 && (
        <>
          <div className="section-title">Historial de ciclos y paquetes archivados</div>
          <div className="card table-scroll"><table className="data-table"><thead><tr>
            <th>Paquete</th><th>Tipo</th><th>Vencía</th><th className="num">Costo</th><th className="num">Pagado</th><th>Estado</th><th></th></tr></thead><tbody>
            {ficha.historial.map((p) => (
              <tr key={p.id} className="clickable-row" onClick={() => { setPaqueteId(p.id); window.scrollTo({ top: 0 }) }}>
                <td>{p.paquete}</td><td>{p.tipo}</td><td>{fecha(p.fecha_renovacion)}</td><td className="num">{dinero(p.costo)}</td>
                <td className="num">{dinero(p.pagado)}{p.restante > 0 && <span className="badge badge-bad" style={{ marginLeft: 6 }}>debe {dinero(p.restante)}</span>}</td>
                <td><span className={`badge ${BADGE_ESTADO[p.estado]}`}>{ESTADO_LABEL[p.estado]}</span></td>
                <td><button className="btn btn-ghost btn-sm">Ver</button></td></tr>))}
          </tbody></table></div>
        </>
      )}
      {modal === 'agregar' && <AgregarPaqueteModal clienteId={ficha.id} onClose={() => setModal(null)} onHecho={(id) => { setModal(null); recargarTodo(id); avisar('Paquete agregado') }} />}
      {toast}
    </div>
  )
}

/* ------------------------------------------------------------------- datos del cliente */
function DatosCliente({ ficha, puedeEscribir, onGuardado, onEliminado }: { ficha: Ficha; puedeEscribir: boolean; onGuardado: (f: Ficha) => void; onEliminado: () => void }) {
  const base = { nombre: ficha.nombre, correo_fb: ficha.correo_fb ?? '', correo_contacto: ficha.correo_contacto ?? '', telefono: ficha.telefono ?? '', observaciones: ficha.observaciones ?? '' }
  const [d, setD] = useState(base)
  const [nuevaPwd, setNuevaPwd] = useState('')
  const [pwdVisible, setPwdVisible] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [borrando, setBorrando] = useState(false)
  const [confirma, setConfirma] = useState('')
  const sucio = JSON.stringify(d) !== JSON.stringify(base) || nuevaPwd !== ''
  const set = (k: keyof typeof d) => (e: { target: { value: string } }) => setD({ ...d, [k]: e.target.value })

  async function guardar() {
    setGuardando(true); setError(null)
    try {
      const f = await api.patch<Ficha>(`/clientes/${ficha.id}`, { ...d, ...(nuevaPwd ? { password_fb: nuevaPwd } : {}) })
      setNuevaPwd(''); setPwdVisible(null); onGuardado(f)
    } catch (e) { setError(msg(e, 'No se pudo guardar')) } finally { setGuardando(false) }
  }
  async function ver() {
    if (pwdVisible !== null) { setPwdVisible(null); return }
    try { setPwdVisible((await api.post<{ password: string }>(`/clientes/${ficha.id}/password-fb/ver`)).password) } catch (e) { setError(msg(e, 'No se pudo mostrar')) }
  }
  async function eliminar() {
    try { await api.del(`/clientes/${ficha.id}?confirmar_nombre=${encodeURIComponent(confirma)}`); onEliminado() } catch (e) { setError(msg(e, 'No se pudo eliminar')) }
  }
  const ro = !puedeEscribir
  return (
    <div className="card" style={{ padding: 20, marginTop: 12 }}>
      <div className="grid-2">
        <div className="field"><label>Nombre del cliente</label><input type="text" value={d.nombre} onChange={set('nombre')} disabled={ro} /></div>
        <div className="field"><label>Teléfono personal</label><input type="text" value={d.telefono} onChange={set('telefono')} disabled={ro} /></div>
        <div className="field"><label>Correo de Facebook</label><input type="text" value={d.correo_fb} onChange={set('correo_fb')} disabled={ro} /></div>
        <div className="field"><label>Contraseña de Facebook</label>
          <div style={{ display: 'flex', gap: 6 }}>
            {ficha.tiene_password_fb && !nuevaPwd
              ? <input type="text" readOnly value={pwdVisible ?? '••••••••••'} style={{ fontFamily: pwdVisible ? 'monospace' : undefined }} />
              : <input type="password" autoComplete="new-password" placeholder={ficha.tiene_password_fb ? 'Nueva contraseña' : 'Sin contraseña guardada'} value={nuevaPwd} onChange={(e) => setNuevaPwd(e.target.value)} disabled={ro} />}
            {ficha.tiene_password_fb && <button className="btn btn-secondary btn-sm" onClick={ver}>{pwdVisible !== null ? 'Ocultar' : 'Ver'}</button>}
            {pwdVisible !== null && <button className="btn btn-secondary btn-sm" onClick={() => copiar(pwdVisible)}>Copiar</button>}
          </div>
          {!ro && ficha.tiene_password_fb && !nuevaPwd && <button className="btn btn-ghost btn-sm" style={{ marginTop: 4, padding: '2px 6px' }} onClick={() => setNuevaPwd(' ')}>Cambiar contraseña</button>}
        </div>
        <div className="field"><label>Correo de contacto</label><input type="text" value={d.correo_contacto} onChange={set('correo_contacto')} disabled={ro} /></div>
      </div>
      <div className="field"><label>Observaciones</label><textarea rows={2} value={d.observaciones} onChange={set('observaciones')} disabled={ro} /></div>
      <ErrorTexto texto={error} />
      {!ro && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" disabled={!sucio || guardando || !d.nombre.trim()} onClick={guardar}>Guardar cambios</button>
          {sucio && <button className="btn btn-ghost" onClick={() => { setD(base); setNuevaPwd('') }}>Descartar</button>}
          <span className="right" />
          {!borrando ? <button className="btn btn-ghost btn-sm" onClick={() => setBorrando(true)}>Eliminar cliente…</button> : (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="text" placeholder={`Escribe «${ficha.nombre}»`} value={confirma} onChange={(e) => setConfirma(e.target.value)} style={{ width: 240 }} />
              <button className="btn btn-danger btn-sm" disabled={confirma !== ficha.nombre} onClick={eliminar}>Eliminar</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setBorrando(false); setConfirma('') }}>Cancelar</button>
            </div>)}
        </div>
      )}
    </div>
  )
}

/* ----------------------------------------------------------------------------- paquetes */
function Paquetes({ ficha, paqueteId, setPaqueteId, puedeEscribir, recargar, sinPaquetes, avisar, onClienteGone }: {
  ficha: Ficha; paqueteId: number | null; setPaqueteId: (id: number) => void; puedeEscribir: boolean
  recargar: (sel?: number | null) => Promise<void>; sinPaquetes: boolean; avisar: (t: string) => void; onClienteGone: () => void
}) {
  const [det, setDet] = useState<PaqueteDetalle | null>(null)
  const [errorDet, setErrorDet] = useState<string | null>(null)
  const [modal, setModal] = useState<'renovar' | 'no' | 'editar' | null>(null)
  const [recordatorio, setRecordatorio] = useState<Recordatorio | null>(null)

  const cargarDet = useCallback(async () => {
    if (paqueteId == null) { setDet(null); return }
    try { setDet(await api.get<PaqueteDetalle>(`/paquetes/${paqueteId}`)); setErrorDet(null) } catch (e) { setErrorDet(msg(e, 'No se pudo cargar el paquete')) }
  }, [paqueteId])
  useEffect(() => { cargarDet() }, [cargarDet])

  const cambio = async (sel?: number | null) => { await recargar(sel ?? paqueteId); await cargarDet() }
  const vigente = det ? ficha.paquetes.some((p) => p.id === det.id) : false

  if (sinPaquetes && !det) return <div className="card" style={{ padding: 20 }}><p className="muted" style={{ margin: 0 }}>Este cliente no tiene paquetes vigentes.</p></div>
  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="field" style={{ maxWidth: 520 }}>
        <label>Paquete del cliente</label>
        <select value={paqueteId ?? ''} onChange={(e) => setPaqueteId(Number(e.target.value))}>
          {ficha.paquetes.map((p) => <option key={p.id} value={p.id}>{p.paquete} · {p.tipo} — renueva {fecha(p.fecha_renovacion)}</option>)}
          {det && !vigente && <option value={det.id}>(Historial) {det.paquete} · {ESTADO_LABEL[det.estado]} — {fecha(det.fecha_renovacion)}</option>}
        </select>
      </div>
      <ErrorTexto texto={errorDet} />
      {det && (
        <>
          {!vigente && <div className="callout callout-info">Estás viendo un ciclo del historial ({ESTADO_LABEL[det.estado].toLowerCase()}). {det.restante > 0 ? 'Aún tiene saldo por cobrar: puedes seguir registrando pagos.' : ''}</div>}
          <div className="kv" style={{ margin: '8px 0 14px' }}>
            <div><div className="k">Tipo</div><div className="v">{det.tipo}</div></div>
            <div><div className="k">Paquete</div><div className="v">{det.paquete}</div></div>
            <div><div className="k">Costo</div><div className="v">{dinero(det.costo)}</div></div>
            <div><div className="k">Pagado</div><div className="v" style={{ color: 'var(--good)' }}>{dinero(det.pagado)}</div></div>
            <div><div className="k">Restante</div><div className="v" style={{ color: det.restante > 0 ? 'var(--warn)' : 'var(--good)' }}>{dinero(det.restante)}</div></div>
            <div><div className="k">Fecha de renovación</div><div className="v">{fecha(det.fecha_renovacion)}</div></div>
            <div><div className="k">Estado</div><div className="v"><span className={`badge ${BADGE_ESTADO[det.estado_efectivo]}`}>{ESTADO_LABEL[det.estado_efectivo]}</span></div></div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <div style={{ flex: 1 }}><Progreso pct={det.avance_pct} /></div>
            <strong style={{ fontSize: 13, minWidth: 120, textAlign: 'right' }}>{dinero(det.pagado)} de {dinero(det.costo)}</strong>
          </div>
          {puedeEscribir && vigente && <div style={{ textAlign: 'right' }}><button className="btn btn-ghost btn-sm" onClick={() => setModal('editar')}>Editar paquete</button></div>}

          <Pagos det={det} puedeEscribir={puedeEscribir} alCambiar={cambio} avisar={avisar} />
          <Prorroga det={det} puedeEscribir={puedeEscribir} alCambiar={cambio} avisar={avisar} />

          <div className="section-title">Renovación</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Semaforo valor={det.semaforo} conTexto />
            {vigente && <span className="muted" style={{ fontSize: 13 }}>· {diasTexto(det.dias_para_renovar)} ({fecha(det.fecha_renovacion)})</span>}
            {det.renovacion_decision !== 'pendiente' && <span className="badge badge-purple">Decisión: {det.renovacion_decision === 'si' ? 'renovó' : 'no renovó'}</span>}
          </div>
          {vigente && det.estado === 'vencido' && <div className="callout callout-bad">Llegó su fecha de renovación sin decisión. Indica si el cliente renovó.</div>}
          {vigente && det.estado_efectivo === 'por_vencer' && <div className="callout callout-warn">Este paquete renueva pronto: pregúntale al cliente si renueva.</div>}
          {puedeEscribir && vigente && (
            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={() => setModal('renovar')}>Renovó</button>
              <button className="btn btn-secondary" onClick={() => setModal('no')}>No renovó</button>
            </div>)}
          {det.restante > 0 && puedeEscribir && (
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-secondary btn-sm" onClick={async () => { try { setRecordatorio(await api.post<Recordatorio>(`/paquetes/${det.id}/recordatorio`)) } catch (e) { avisar(msg(e, 'No se pudo generar')) } }}>
                Recordatorio de pago al cliente</button>
            </div>)}
          {det.renovaciones.length > 0 && (
            <>
              <div className="section-title">Historial de renovaciones de este paquete</div>
              <table className="data-table"><thead><tr><th>Fecha</th><th className="num">Costo anterior</th><th className="num">Costo nuevo</th><th>Cambio</th></tr></thead><tbody>
                {det.renovaciones.map((r) => <tr key={r.id}><td>{fecha(r.fecha)}</td><td className="num">{dinero(r.costo_anterior)}</td><td className="num">{dinero(r.costo_nuevo)}</td>
                  <td>{r.paquete_anterior_id === r.paquete_nuevo_id ? 'Mismo paquete' : 'Cambió de paquete'}</td></tr>)}
              </tbody></table>
            </>)}
          <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>Semáforo: {SEMAFORO_LABEL[det.semaforo]}. Ciclo del {fecha(det.fecha_inicio)} al {fecha(det.fecha_renovacion)}.</p>

          {modal === 'renovar' && <RenovarModal p={det as Paquete} onClose={() => setModal(null)} onHecho={(id) => { setModal(null); cambio(id); avisar('Renovado: se abrió un ciclo nuevo') }} />}
          {modal === 'editar' && <EditarPaqueteModal p={det as Paquete} onClose={() => setModal(null)} onHecho={() => { setModal(null); cambio(); avisar('Paquete actualizado') }} />}
          {modal === 'no' && <NoRenovarModal p={det as Paquete} esUltimo={ficha.paquetes.length === 1} nombreCliente={ficha.nombre} onClose={() => setModal(null)}
            onHecho={(r) => { setModal(null); if (r.cliente_eliminado) onClienteGone(); else { cambio(); avisar(r.cliente_a_no_renovados ? 'El cliente pasó a No renovados' : 'Paquete actualizado') } }} />}
          {recordatorio && <RecordatorioModal r={recordatorio} onClose={() => setRecordatorio(null)} />}
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------------------- pagos */
function Pagos({ det, puedeEscribir, alCambiar, avisar }: { det: PaqueteDetalle; puedeEscribir: boolean; alCambiar: () => Promise<void>; avisar: (t: string) => void }) {
  const [monto, setMonto] = useState('')
  const [fechaPago, setFechaPago] = useState(hoyIso())
  const [nota, setNota] = useState('')
  const [error, setError] = useState<string | null>(null)
  const puedePagar = puedeEscribir && ['activo', 'vencido', 'renovado'].includes(det.estado) && det.restante > 0

  async function registrar() {
    setError(null)
    try { await api.post(`/paquetes/${det.id}/pagos`, { monto: Number(monto), fecha: fechaPago, nota: nota || null }); setMonto(''); setNota(''); await alCambiar(); avisar('Pago registrado') }
    catch (e) { setError(msg(e, 'No se pudo registrar el pago')) }
  }
  async function borrar(id: number) {
    if (!confirm('¿Borrar este pago? Queda en la bitácora.')) return
    try { await api.del(`/pagos/${id}`); await alCambiar() } catch (e) { avisar(msg(e, 'No se pudo borrar')) }
  }
  return (
    <>
      <div className="section-title">Pagos</div>
      {det.pagos.length === 0 ? <p className="muted" style={{ margin: '0 0 8px' }}>Aún no hay pagos registrados.</p> : (
        <table className="data-table"><thead><tr><th>Fecha</th><th className="num">Monto</th><th>Registró</th><th>Nota</th><th></th></tr></thead><tbody>
          {det.pagos.map((g) => <tr key={g.id}><td>{fecha(g.fecha)}</td><td className="num">{dinero(g.monto)}</td><td>{g.registrado_por_nombre ?? '—'}</td><td className="muted">{g.nota ?? ''}</td>
            <td>{puedeEscribir && <button className="btn btn-ghost btn-sm" title="Borrar pago" onClick={() => borrar(g.id)}>✕</button>}</td></tr>)}
        </tbody></table>)}
      {puedePagar && (
        <div className="row" style={{ marginTop: 10 }}>
          <div className="field" style={{ maxWidth: 160 }}><label>Monto (parcial o total)</label><input type="number" min="0" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder={String(det.restante)} /></div>
          <div className="field" style={{ maxWidth: 170 }}><label>Fecha</label><input type="date" max={hoyIso()} value={fechaPago} onChange={(e) => setFechaPago(e.target.value)} /></div>
          <div className="field"><label>Nota (opcional)</label><input type="text" value={nota} onChange={(e) => setNota(e.target.value)} /></div>
          <button className="btn btn-primary" disabled={!Number(monto)} onClick={registrar}>Registrar pago</button>
          {det.restante > 0 && <button className="btn btn-ghost btn-sm" onClick={() => setMonto(String(det.restante))}>Pagar el total</button>}
        </div>)}
      <ErrorTexto texto={error} />
    </>
  )
}

/* ----------------------------------------------------------------------------- prórroga */
function Prorroga({ det, puedeEscribir, alCambiar, avisar }: { det: PaqueteDetalle; puedeEscribir: boolean; alCambiar: () => Promise<void>; avisar: (t: string) => void }) {
  const { user } = useAuth()
  const hoy = hoyIso(), maximo = sumarDias(hoy, 15)
  const [hasta, setHasta] = useState(sumarDias(hoy, 7))
  const [editando, setEditando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (det.restante <= 0 && !det.prorroga_hasta) return null
  const puedeRegistrar = puedeEscribir && ['activo', 'vencido', 'renovado'].includes(det.estado) && det.restante > 0 &&
    (!det.prorroga_hasta || (user?.rol === 'admin' && editando))

  async function guardar() {
    setError(null)
    try { await api.put(`/paquetes/${det.id}/prorroga`, { hasta }); setEditando(false); await alCambiar(); avisar('Prórroga registrada') }
    catch (e) { setError(msg(e, 'No se pudo registrar la prórroga')) }
  }
  return (
    <>
      <div className="section-title">Prórroga</div>
      {det.requiere_prorroga && <div className="callout callout-bad">Terminó la tolerancia de 3 días y el cliente aún debe {dinero(det.restante)}: registra hasta cuándo le diste plazo.</div>}
      {det.prorroga_hasta && (
        <div className={`callout ${det.prorroga_vencida ? 'callout-bad' : 'callout-warn'}`}>
          Prórroga hasta el <strong>{fecha(det.prorroga_hasta)}</strong> (registrada el {fecha(det.prorroga_registrada_en)}).{' '}
          {det.restante <= 0 ? 'Ya se pagó completo.' : det.prorroga_vencida ? `Venció hace ${-(det.prorroga_dias_restantes ?? 0)} día(s) y aún faltan ${dinero(det.restante)}.` : `${diasTexto(det.prorroga_dias_restantes ?? 0)}; faltan ${dinero(det.restante)}.`}
          {user?.rol === 'admin' && puedeEscribir && det.restante > 0 && !editando && <button className="btn btn-ghost btn-sm" onClick={() => setEditando(true)}>Cambiar (admin)</button>}
        </div>)}
      {puedeRegistrar && (
        <div className="row">
          <div className="field" style={{ maxWidth: 200 }}><label>Plazo hasta (máx. 15 días naturales)</label>
            <input type="date" min={hoy} max={maximo} value={hasta} onChange={(e) => setHasta(e.target.value)} /></div>
          <button className="btn btn-secondary" onClick={guardar} disabled={!hasta}>Registrar prórroga</button>
        </div>)}
      {!det.prorroga_hasta && !puedeRegistrar && det.restante > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Si el cliente no completa el pago, registra aquí la prórroga que le diste.</p>}
      <ErrorTexto texto={error} />
    </>
  )
}

