import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { CatalogoItem } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Cargando, ErrorTexto } from '../../components/ui'

export default function CatalogosView() {
  return (
    <div>
      <h1 className="page-title">Catálogos</h1>
      <p className="page-sub">Paquetes y tipos que aparecen al capturar un paquete. Lo desactivado deja de ofrecerse, pero no se pierde de los clientes que ya lo tienen.</p>
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <Lista tabla="paquetes" titulo="Paquetes" /><Lista tabla="tipos" titulo="Tipos" />
      </div>
    </div>
  )
}

function Lista({ tabla, titulo }: { tabla: 'paquetes' | 'tipos'; titulo: string }) {
  const { puedeEscribir } = useAuth()
  const [items, setItems] = useState<CatalogoItem[] | null>(null)
  const [nuevo, setNuevo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const cargar = useCallback(() => api.get<CatalogoItem[]>(`/catalogos/${tabla}?todos=true`).then(setItems), [tabla])
  useEffect(() => { cargar() }, [cargar])
  const run = async (f: () => Promise<unknown>) => { setError(null); try { await f(); await cargar() } catch (e) { setError(e instanceof ApiError ? e.message : 'Error') } }
  if (!items) return <Cargando />
  return (
    <div className="card" style={{ padding: 18 }}>
      <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>{titulo}</h2>
      {items.map((i) => (
        <div key={i.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, opacity: i.activo ? 1 : 0.55 }}>
          <input type="number" aria-label="Orden" style={{ width: 64 }} defaultValue={i.orden} disabled={!puedeEscribir}
            onBlur={(e) => Number(e.target.value) !== i.orden && run(() => api.patch(`/catalogos/${tabla}/${i.id}`, { orden: Number(e.target.value) }))} />
          <input type="text" aria-label="Nombre" defaultValue={i.nombre} disabled={!puedeEscribir}
            onBlur={(e) => e.target.value.trim() && e.target.value !== i.nombre && run(() => api.patch(`/catalogos/${tabla}/${i.id}`, { nombre: e.target.value }))} />
          {puedeEscribir && <button className="btn btn-secondary btn-sm" onClick={() => run(() => api.patch(`/catalogos/${tabla}/${i.id}`, { activo: !i.activo }))}>{i.activo ? 'Desactivar' : 'Activar'}</button>}
        </div>))}
      {puedeEscribir && (
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <input type="text" placeholder={`Nuevo ${tabla === 'paquetes' ? 'paquete' : 'tipo'}…`} value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
          <button className="btn btn-primary" disabled={!nuevo.trim()} onClick={() => run(async () => { await api.post(`/catalogos/${tabla}`, { nombre: nuevo }); setNuevo('') })}>Agregar</button>
        </div>)}
      {tabla === 'paquetes' && <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>El orden define «subir/bajar de nivel» al renovar.</p>}
      <ErrorTexto texto={error} />
    </div>
  )
}
