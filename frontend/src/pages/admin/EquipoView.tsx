import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { UsuarioEquipo } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Cargando, ErrorTexto, Modal, PasswordUnaVez } from '../../components/ui'
import { fecha } from '../../util'

interface Creds { titulo: string; username: string; password: string }

export default function EquipoView({ onCambio }: { onCambio: () => void }) {
  const { user, puedeEscribir } = useAuth()
  const [lista, setLista] = useState<UsuarioEquipo[] | null>(null)
  const [alta, setAlta] = useState(false)
  const [creds, setCreds] = useState<Creds | null>(null)
  const [baja, setBaja] = useState<UsuarioEquipo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const cargar = useCallback(() => api.get<UsuarioEquipo[]>('/usuarios').then(setLista), [])
  useEffect(() => { cargar() }, [cargar])

  async function reset(u: UsuarioEquipo) {
    if (!confirm(`¿Generar una contraseña nueva para ${u.nombre}? La anterior dejará de servir.`)) return
    try { const r = await api.post<{ username: string; password: string }>(`/usuarios/${u.id}/reset-password`); setCreds({ titulo: 'Nueva contraseña', ...r }) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo resetear') }
  }
  if (!lista) return <Cargando />
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div><h1 className="page-title">Equipo</h1><p className="page-sub" style={{ margin: 0 }}>CMs y administradores. Las contraseñas las genera el sistema (18 caracteres) y se muestran una sola vez.</p></div>
        {puedeEscribir && <button className="btn btn-primary right" onClick={() => setAlta(true)}>+ Agregar usuario</button>}
      </div>
      <ErrorTexto texto={error} />
      <div className="card table-scroll" style={{ marginTop: 18 }}><table className="data-table"><thead><tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Estado</th><th className="num">Clientes activos</th><th className="num">No renovados</th><th>Alta</th><th></th></tr></thead><tbody>
        {lista.map((u) => (
          <tr key={u.id} style={{ opacity: u.activo ? 1 : 0.55 }}>
            <td><strong>{u.nombre}</strong>{u.id === user?.id && <span className="badge badge-purple" style={{ marginLeft: 6 }}>tú</span>}</td><td>{u.username}</td>
            <td>{u.rol === 'cm' ? 'CM' : u.solo_lectura ? 'Admin · solo lectura' : 'Admin'}</td>
            <td>{u.activo ? <span className="badge badge-good">Activo</span> : <span className="badge badge-neutral">De baja</span>}</td>
            <td className="num">{u.rol === 'cm' ? u.clientes_activos : '—'}</td><td className="num">{u.rol === 'cm' ? u.clientes_no_renovados : '—'}</td><td>{fecha(u.creado_en)}</td>
            <td className="num" style={{ whiteSpace: 'nowrap' }}>{puedeEscribir && u.activo && <>
              <button className="btn btn-secondary btn-sm" onClick={() => reset(u)}>Resetear contraseña</button>{' '}
              {u.id !== user?.id && <button className="btn btn-danger btn-sm" onClick={() => setBaja(u)}>Dar de baja</button>}</>}</td></tr>))}
      </tbody></table></div>
      {alta && <Alta onClose={() => setAlta(false)} onHecho={(c) => { setAlta(false); setCreds(c); cargar(); onCambio() }} />}
      {baja && <Baja u={baja} cms={lista.filter((x) => x.rol === 'cm' && x.activo && x.id !== baja.id)} onClose={() => setBaja(null)} onHecho={() => { setBaja(null); cargar(); onCambio() }} />}
      {creds && <PasswordUnaVez {...creds} onClose={() => setCreds(null)} />}
    </div>
  )
}

function Alta({ onClose, onHecho }: { onClose: () => void; onHecho: (c: Creds) => void }) {
  const [nombre, setNombre] = useState('')
  const [rol, setRol] = useState<'cm' | 'admin'>('cm')
  const [soloLectura, setSoloLectura] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function crear() {
    setError(null)
    try { const r = await api.post<{ username: string; password: string }>('/usuarios', { nombre, rol, solo_lectura: rol === 'admin' && soloLectura }); onHecho({ titulo: 'Usuario creado', ...r }) }
    catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo crear') }
  }
  return (
    <Modal title="Agregar usuario" onClose={onClose} width={460}>
      <div className="field"><label>Nombre completo</label><input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus placeholder="Ej. María López" /></div>
      <div className="field"><label>Rol</label>
        <div className="segmented light full"><button className={rol === 'cm' ? 'active' : ''} onClick={() => setRol('cm')}>CM</button><button className={rol === 'admin' ? 'active' : ''} onClick={() => setRol('admin')}>Administrador</button></div></div>
      {rol === 'admin' && <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600 }}><input type="checkbox" style={{ width: 'auto' }} checked={soloLectura} onChange={(e) => setSoloLectura(e.target.checked)} /> Solo lectura (ve y descarga reportes, no edita)</label>}
      <ErrorTexto texto={error} />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
        <button className="btn btn-secondary" onClick={onClose}>Cancelar</button><button className="btn btn-primary" disabled={nombre.trim().length < 2} onClick={crear}>Crear usuario</button></div>
    </Modal>
  )
}

function Baja({ u, cms, onClose, onHecho }: { u: UsuarioEquipo; cms: UsuarioEquipo[]; onClose: () => void; onHecho: () => void }) {
  const total = u.clientes_activos + u.clientes_no_renovados
  const [destino, setDestino] = useState<string>('')   // '' = elegir · 'por' = por reasignar · id
  const [error, setError] = useState<string | null>(null)
  async function enviar() {
    setError(null)
    try { await api.post(`/usuarios/${u.id}/baja`, { migrar_a_cm_id: destino && destino !== 'por' ? Number(destino) : null, dejar_por_reasignar: destino === 'por' }); onHecho() }
    catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo dar de baja') }
  }
  const necesitaDestino = u.rol === 'cm' && total > 0
  return (
    <Modal title={`Dar de baja a ${u.nombre}`} onClose={onClose} width={500}>
      {necesitaDestino ? (
        <>
          <div className="callout callout-warn">Tiene <strong>{total} cliente(s)</strong> ({u.clientes_activos} activos, {u.clientes_no_renovados} en No renovados). Su cartera completa se migra para no perder nada.</div>
          <div className="field"><label>Migrar su cartera a…</label>
            <select value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">Elige un CM…</option>{cms.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}<option value="por">Clientes por reasignar (decidir después)</option></select></div>
        </>) : <p style={{ marginTop: 0 }}>{u.rol === 'cm' ? 'No tiene clientes que migrar.' : 'Dejará de poder entrar al sistema.'} Esta acción queda en la bitácora.</p>}
      <ErrorTexto texto={error} />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
        <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
        <button className="btn btn-danger" disabled={necesitaDestino && !destino} onClick={enviar}>Dar de baja</button></div>
    </Modal>
  )
}
