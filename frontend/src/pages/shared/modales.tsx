import { useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { CatalogoItem, Paquete } from '../../api/types'
import { ErrorTexto, Modal } from '../../components/ui'
import { dinero, fecha, hoyIso, sumarDias } from '../../util'

export function useCatalogos() {
  const [paquetes, setPaquetes] = useState<CatalogoItem[]>([])
  const [tipos, setTipos] = useState<CatalogoItem[]>([])
  useEffect(() => {
    api.get<CatalogoItem[]>('/catalogos/paquetes').then(setPaquetes)
    api.get<CatalogoItem[]>('/catalogos/tipos').then(setTipos)
  }, [])
  return { paquetes, tipos }
}

const msg = (e: unknown, def: string) => (e instanceof ApiError ? e.message : def)

function Botones({ onClose, onOk, okText, disabled, danger }: { onClose: () => void; onOk: () => void; okText: string; disabled?: boolean; danger?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
      <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
      <button className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onOk} disabled={disabled}>{okText}</button>
    </div>
  )
}

/* ------------------------------------------------------------------ agregar / editar paquete */
export function CamposPaquete({ v, set, paquetes, tipos }: {
  v: { paquete_id: string; tipo_id: string; costo: string; fecha_renovacion: string }
  set: (v: { paquete_id: string; tipo_id: string; costo: string; fecha_renovacion: string }) => void
  paquetes: CatalogoItem[]; tipos: CatalogoItem[]
}) {
  return (
    <>
      <div className="grid-2">
        <div className="field"><label>Paquete</label>
          <select value={v.paquete_id} onChange={(e) => set({ ...v, paquete_id: e.target.value })}>
            <option value="">Elige…</option>{paquetes.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select></div>
        <div className="field"><label>Tipo</label>
          <select value={v.tipo_id} onChange={(e) => set({ ...v, tipo_id: e.target.value })}>
            <option value="">Elige…</option>{tipos.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
          </select></div>
        <div className="field"><label>Costo</label>
          <input type="number" min="0" step="0.01" value={v.costo} onChange={(e) => set({ ...v, costo: e.target.value })} /></div>
        <div className="field"><label>Fecha de renovación</label>
          <input type="date" value={v.fecha_renovacion} onChange={(e) => set({ ...v, fecha_renovacion: e.target.value })} /></div>
      </div>
    </>
  )
}

export const paqueteVacio = () => ({ paquete_id: '', tipo_id: '', costo: '', fecha_renovacion: sumarDias(hoyIso(), 30) })
export const paqueteCompleto = (v: ReturnType<typeof paqueteVacio>) => !!(v.paquete_id && v.tipo_id && v.costo !== '' && v.fecha_renovacion)
export const paqueteBody = (v: ReturnType<typeof paqueteVacio>) => ({ paquete_id: Number(v.paquete_id), tipo_id: Number(v.tipo_id), costo: Number(v.costo), fecha_renovacion: v.fecha_renovacion })

export function AgregarPaqueteModal({ clienteId, onClose, onHecho }: { clienteId: number; onClose: () => void; onHecho: (nuevoId: number) => void }) {
  const cat = useCatalogos()
  const [v, setV] = useState(paqueteVacio())
  const [error, setError] = useState<string | null>(null)
  async function guardar() {
    setError(null)
    try { const r = await api.post<{ id: number }>(`/clientes/${clienteId}/paquetes`, paqueteBody(v)); onHecho(r.id) }
    catch (e) { setError(msg(e, 'No se pudo agregar el paquete')) }
  }
  return (
    <Modal title="Agregar paquete" onClose={onClose} width={520}>
      <p className="muted" style={{ marginTop: 0 }}>Cada paquete tiene su propio costo, pagos y fecha de renovación.</p>
      <CamposPaquete v={v} set={setV} {...cat} />
      <ErrorTexto texto={error} />
      <Botones onClose={onClose} onOk={guardar} okText="Agregar" disabled={!paqueteCompleto(v)} />
    </Modal>
  )
}

export function EditarPaqueteModal({ p, onClose, onHecho }: { p: Paquete; onClose: () => void; onHecho: () => void }) {
  const cat = useCatalogos()
  const [v, setV] = useState({ paquete_id: String(p.paquete_id), tipo_id: String(p.tipo_id), costo: String(p.costo), fecha_renovacion: p.fecha_renovacion })
  const [error, setError] = useState<string | null>(null)
  async function guardar() {
    setError(null)
    try { await api.patch(`/paquetes/${p.id}`, paqueteBody(v)); onHecho() } catch (e) { setError(msg(e, 'No se pudo guardar')) }
  }
  return (
    <Modal title="Editar paquete" onClose={onClose} width={520}>
      <CamposPaquete v={v} set={setV} {...cat} />
      <div className="callout callout-info">Cambiar costo o fecha queda registrado en la bitácora.</div>
      <ErrorTexto texto={error} />
      <Botones onClose={onClose} onOk={guardar} okText="Guardar" disabled={!paqueteCompleto(v)} />
    </Modal>
  )
}

/* -------------------------------------------------------------------------------- renovar */
export function RenovarModal({ p, onClose, onHecho }: { p: Paquete; onClose: () => void; onHecho: (nuevoId: number) => void }) {
  const cat = useCatalogos()
  const [cambiar, setCambiar] = useState(false)
  const [paqueteId, setPaqueteId] = useState(String(p.paquete_id))
  const [tipoId, setTipoId] = useState(String(p.tipo_id))
  const [costo, setCosto] = useState(String(p.costo))
  const [nuevaFecha, setNuevaFecha] = useState(sumarDias(p.fecha_renovacion, 30))
  const [error, setError] = useState<string | null>(null)
  const actual = cat.paquetes.find((x) => x.id === p.paquete_id)
  const elegido = cat.paquetes.find((x) => x.id === Number(paqueteId))
  const nivel = actual && elegido && elegido.orden !== actual.orden ? (elegido.orden > actual.orden ? 'Subir de nivel' : 'Bajar de nivel') : null

  async function guardar() {
    setError(null)
    try {
      const body = cambiar ? { paquete_id: Number(paqueteId), tipo_id: Number(tipoId), costo: Number(costo), fecha_renovacion: nuevaFecha } : { fecha_renovacion: nuevaFecha }
      const r = await api.post<{ nuevo: Paquete }>(`/paquetes/${p.id}/renovar`, body)
      onHecho(r.nuevo.id)
    } catch (e) { setError(msg(e, 'No se pudo renovar')) }
  }
  return (
    <Modal title={`Renovó · ${p.paquete}`} onClose={onClose} width={540}>
      <div className="callout callout-info">
        Se cierra este ciclo (conserva sus pagos y lo que se deba) y se abre uno nuevo con <strong>pagado en $0</strong>.
        El ciclo anterior queda en el historial de renovaciones.
        {cambiar && ' Al cambiar de paquete, el conteo de renovaciones del paquete se reinicia en 0 y se usan los datos nuevos (paquete, tipo y costo).'}
      </div>
      <div className="segmented light full" style={{ marginBottom: 14 }}>
        <button className={!cambiar ? 'active' : ''} onClick={() => setCambiar(false)}>Mantener el mismo paquete</button>
        <button className={cambiar ? 'active' : ''} onClick={() => setCambiar(true)}>Cambiar de paquete</button>
      </div>
      {cambiar && (
        <div className="grid-2">
          <div className="field"><label>Paquete nuevo</label>
            <select value={paqueteId} onChange={(e) => setPaqueteId(e.target.value)}>{cat.paquetes.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select>
            {nivel && <span className={`badge ${nivel === 'Subir de nivel' ? 'badge-good' : 'badge-warn'}`} style={{ marginTop: 6 }}>{nivel}</span>}</div>
          <div className="field"><label>Tipo</label>
            <select value={tipoId} onChange={(e) => setTipoId(e.target.value)}>{cat.tipos.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}</select></div>
          <div className="field"><label>Nuevo costo</label><input type="number" min="0" step="0.01" value={costo} onChange={(e) => setCosto(e.target.value)} /></div>
        </div>
      )}
      {!cambiar && <p className="muted" style={{ marginTop: 0 }}>Mismo paquete, tipo y costo ({dinero(p.costo)}).</p>}
      <div className="field"><label>Nueva fecha de renovación</label>
        <input type="date" min={sumarDias(p.fecha_renovacion, 1)} value={nuevaFecha} onChange={(e) => setNuevaFecha(e.target.value)} />
        <span className="muted" style={{ fontSize: 12 }}>Sugerida: 30 días después de {fecha(p.fecha_renovacion)}.</span></div>
      <ErrorTexto texto={error} />
      <Botones onClose={onClose} onOk={guardar} okText="Renovar" disabled={!nuevaFecha || (cambiar && (!costo || !paqueteId || !tipoId))} />
    </Modal>
  )
}

/* ----------------------------------------------------------------------------- no renovar */
export function NoRenovarModal({ p, esUltimo, nombreCliente, onClose, onHecho }: {
  p: Paquete; esUltimo: boolean; nombreCliente: string; onClose: () => void; onHecho: (r: { cliente_eliminado: boolean; cliente_a_no_renovados: boolean }) => void
}) {
  const [accion, setAccion] = useState<'conservar' | 'borrar'>('conservar')
  const [confirma, setConfirma] = useState('')
  const [preguntaCliente, setPreguntaCliente] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function enviar(eliminarCliente?: boolean) {
    setError(null)
    try {
      const r = await api.post<{ cliente_eliminado: boolean; cliente_a_no_renovados: boolean }>(`/paquetes/${p.id}/no-renovar`,
        { accion, confirmar_nombre: accion === 'borrar' ? confirma : null, eliminar_cliente: eliminarCliente ?? null })
      onHecho(r)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ultimo_paquete') setPreguntaCliente(true)
      else setError(msg(e, 'No se pudo completar'))
    }
  }

  if (preguntaCliente) return (
    <Modal title="Es el último paquete" onClose={onClose} width={500}>
      <p style={{ marginTop: 0 }}>«{p.paquete}» es el último paquete de <strong>{nombreCliente}</strong>. ¿También quieres eliminar al cliente?</p>
      <div className="callout callout-bad">Eliminar al cliente borra de forma permanente su ficha, pagos e historial.</div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
        <button className="btn btn-secondary" onClick={() => enviar(false)}>No, pasar a No renovados</button>
        <button className="btn btn-danger" onClick={() => enviar(true)}>Sí, eliminar también al cliente</button>
      </div>
      <ErrorTexto texto={error} />
    </Modal>
  )

  return (
    <Modal title={`No renovó · ${p.paquete}`} onClose={onClose} width={520}>
      <div className="segmented light full" style={{ marginBottom: 14 }}>
        <button className={accion === 'conservar' ? 'active' : ''} onClick={() => setAccion('conservar')}>Conservar en historial</button>
        <button className={accion === 'borrar' ? 'active' : ''} onClick={() => setAccion('borrar')}>Borrar paquete</button>
      </div>
      {accion === 'conservar' ? (
        <div className="callout callout-info">
          El paquete pasa a <strong>archivado</strong> dentro del historial del cliente.
          {esUltimo
            ? ' Como es su último paquete activo, el cliente completo pasará a «No renovados» (se conserva 3 meses y luego se elimina).'
            : ' El cliente sigue activo con sus otros paquetes.'}
        </div>
      ) : (
        <>
          <div className="callout callout-bad">Borrar quita el paquete del cliente. Para confirmar, escribe el nombre exacto del paquete: <strong>{p.paquete}</strong></div>
          <div className="field"><input type="text" placeholder={p.paquete} value={confirma} onChange={(e) => setConfirma(e.target.value)} autoFocus /></div>
        </>
      )}
      <ErrorTexto texto={error} />
      <Botones onClose={onClose} onOk={() => enviar()} danger={accion === 'borrar'}
        okText={accion === 'borrar' ? 'Borrar paquete' : 'Marcar como no renovado'} disabled={accion === 'borrar' && confirma !== p.paquete} />
    </Modal>
  )
}

/* -------------------------------------------------------------------------- agregar cliente */
export function AgregarClienteModal({ onClose, onHecho, cms }: { onClose: () => void; onHecho: (id: number) => void; cms?: { id: number; nombre: string }[] }) {
  const cat = useCatalogos()
  const [d, setD] = useState({ nombre: '', correo_fb: '', password_fb: '', correo_contacto: '', telefono: '', observaciones: '' })
  const [cmId, setCmId] = useState('')
  const [conPaquete, setConPaquete] = useState(true)
  const [pq, setPq] = useState(paqueteVacio())
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof d) => (e: { target: { value: string } }) => setD({ ...d, [k]: e.target.value })

  async function guardar() {
    setError(null)
    try {
      const r = await api.post<{ id: number }>('/clientes', { ...d, cm_id: cms ? (cmId ? Number(cmId) : null) : undefined, paquetes: conPaquete ? [paqueteBody(pq)] : [] })
      onHecho(r.id)
    } catch (e) { setError(msg(e, 'No se pudo crear el cliente')) }
  }
  return (
    <Modal title="Agregar cliente" onClose={onClose} width={640}>
      <div className="grid-2">
        <div className="field"><label>Nombre del cliente *</label><input type="text" value={d.nombre} onChange={set('nombre')} autoFocus /></div>
        <div className="field"><label>Teléfono personal</label><input type="text" value={d.telefono} onChange={set('telefono')} placeholder="10 dígitos" /></div>
        <div className="field"><label>Correo de Facebook</label><input type="text" value={d.correo_fb} onChange={set('correo_fb')} /></div>
        <div className="field"><label>Contraseña de Facebook</label><input type="password" autoComplete="new-password" value={d.password_fb} onChange={set('password_fb')} /></div>
        <div className="field"><label>Correo de contacto</label><input type="text" value={d.correo_contacto} onChange={set('correo_contacto')} /></div>
        {cms && <div className="field"><label>CM responsable</label>
          <select value={cmId} onChange={(e) => setCmId(e.target.value)}><option value="">Por reasignar</option>{cms.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></div>}
      </div>
      <div className="field"><label>Observaciones</label><textarea rows={2} value={d.observaciones} onChange={set('observaciones')} /></div>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600 }}>
        <input type="checkbox" style={{ width: 'auto' }} checked={conPaquete} onChange={(e) => setConPaquete(e.target.checked)} /> Agregar su primer paquete ahora
      </label>
      {conPaquete && <div style={{ marginTop: 10 }}><CamposPaquete v={pq} set={setPq} {...cat} /></div>}
      <ErrorTexto texto={error} />
      <Botones onClose={onClose} onOk={guardar} okText="Crear cliente" disabled={!d.nombre.trim() || (conPaquete && !paqueteCompleto(pq))} />
    </Modal>
  )
}
