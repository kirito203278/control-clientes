import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { ClienteFicha, ClienteListItem } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Cargando, ErrorTexto, Modal } from '../../components/ui'
import { fecha } from '../../util'
import { CamposPaquete, paqueteBody, paqueteCompleto, paqueteVacio, useCatalogos } from './modales'

interface Info { archivado_en: string; forzar_nuevo: boolean; reingreso_meses: number; purga_meses: number; se_elimina_el: string }

export default function NoRenovados({ onAbrir, onCambio }: { onAbrir: (id: number) => void; onCambio: () => void }) {
  const { puedeEscribir, user } = useAuth()
  const [lista, setLista] = useState<ClienteListItem[] | null>(null)
  const [infos, setInfos] = useState<Record<number, Info>>({})
  const [reingresando, setReingresando] = useState<ClienteListItem | null>(null)
  const cargar = useCallback(async () => {
    const l = await api.get<ClienteListItem[]>('/clientes?estado=no_renovado')
    setLista(l)
    const entradas = await Promise.all(l.map(async (c) => [c.id, await api.get<Info>(`/clientes/${c.id}/reingreso-info`)] as const))
    setInfos(Object.fromEntries(entradas))
  }, [])
  useEffect(() => { cargar() }, [cargar])
  if (!lista) return <Cargando />
  return (
    <div>
      <h1 className="page-title">No renovados</h1>
      <p className="page-sub">Clientes sin ningún paquete activo. Se conservan 3 meses con toda su información y después se eliminan de forma permanente.</p>
      {lista.length === 0 ? <div className="card" style={{ padding: 24 }}><p className="muted" style={{ margin: 0 }}>No hay clientes sin renovar.</p></div> : (
        <div className="card table-scroll"><table className="data-table"><thead><tr><th>Cliente</th>{user?.rol === 'admin' && <th>CM</th>}<th>No renovó desde</th><th>Se elimina el</th><th>Reingreso</th><th></th></tr></thead><tbody>
          {lista.map((c) => { const i = infos[c.id]; return (
            <tr key={c.id}><td><button className="btn btn-ghost btn-sm" style={{ fontWeight: 700 }} onClick={() => onAbrir(c.id)}>{c.nombre}</button></td>
              {user?.rol === 'admin' && <td>{c.cm_nombre ?? 'Por reasignar'}</td>}
              <td>{i ? fecha(i.archivado_en) : '…'}</td><td>{i ? fecha(i.se_elimina_el) : '…'}</td>
              <td>{i && (i.forzar_nuevo ? <span className="badge badge-warn">Paquete nuevo (se borra historial)</span> : <span className="badge badge-good">Puede continuar o crear nuevo</span>)}</td>
              <td className="num">{puedeEscribir && <button className="btn btn-primary btn-sm" onClick={() => setReingresando(c)}>Reingresar</button>}</td></tr>) })}
        </tbody></table></div>)}
      {reingresando && infos[reingresando.id] && <Reingreso c={reingresando} info={infos[reingresando.id]} onClose={() => setReingresando(null)}
        onHecho={() => { setReingresando(null); cargar(); onCambio() }} />}
    </div>
  )
}

function Reingreso({ c, info, onClose, onHecho }: { c: ClienteListItem; info: Info; onClose: () => void; onHecho: () => void }) {
  const cat = useCatalogos()
  const [modo, setModo] = useState<'continuar' | 'nuevo'>(info.forzar_nuevo ? 'nuevo' : 'continuar')
  const [pq, setPq] = useState(paqueteVacio())
  const [fechaCont, setFechaCont] = useState(paqueteVacio().fecha_renovacion)
  const [error, setError] = useState<string | null>(null)
  async function enviar() {
    setError(null)
    try {
      await api.post<ClienteFicha>(`/clientes/${c.id}/reingreso`, modo === 'continuar' ? { modo, fecha_renovacion: fechaCont } : { modo, ...paqueteBody(pq) })
      onHecho()
    } catch (e) { setError(e instanceof ApiError ? e.message : 'No se pudo reingresar') }
  }
  return (
    <Modal title={`Reingresar a ${c.nombre}`} onClose={onClose} width={560}>
      {info.forzar_nuevo ? (
        <div className="callout callout-warn">Pasaron {info.reingreso_meses} meses o más desde que no renovó: se crea un <strong>paquete nuevo</strong> y el
          <strong> historial anterior se borra</strong> (paquetes y pagos).</div>
      ) : (
        <div className="segmented light full" style={{ marginBottom: 14 }}>
          <button className={modo === 'continuar' ? 'active' : ''} onClick={() => setModo('continuar')}>Continuar el paquete anterior</button>
          <button className={modo === 'nuevo' ? 'active' : ''} onClick={() => setModo('nuevo')}>Crear paquete nuevo</button>
        </div>)}
      {modo === 'continuar' ? (
        <div className="field"><label>Nueva fecha de renovación</label><input type="date" value={fechaCont} onChange={(e) => setFechaCont(e.target.value)} />
          <span className="muted" style={{ fontSize: 12 }}>Mismo paquete, tipo y costo; el historial se conserva.</span></div>
      ) : <CamposPaquete v={pq} set={setPq} {...cat} />}
      {modo === 'nuevo' && !info.forzar_nuevo && <p className="muted" style={{ fontSize: 13 }}>El historial anterior se conserva.</p>}
      <ErrorTexto texto={error} />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
        <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" onClick={enviar} disabled={modo === 'nuevo' ? !paqueteCompleto(pq) : !fechaCont}>Reingresar cliente</button>
      </div>
    </Modal>
  )
}
