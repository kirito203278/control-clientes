import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import Logo from '../../components/Logo'
import NotificationBell from '../../components/NotificationBell'
import { api } from '../../api/client'
import { useEffect } from 'react'
import type { UsuarioEquipo } from '../../api/types'
import Ingresos from '../shared/Ingresos'
import NoRenovados from '../shared/NoRenovados'
import Reportes from '../shared/Reportes'
import Tablero from '../shared/Tablero'
import BitacoraView from './BitacoraView'
import CarteraView from './CarteraView'
import CatalogosView from './CatalogosView'
import EquipoView from './EquipoView'

type Vista = 'cartera' | 'renovaciones' | 'ingresos' | 'reportes' | 'no_renovados' | 'equipo' | 'catalogos' | 'bitacora'
const NAV: [Vista, string][] = [['cartera', 'Cartera'], ['renovaciones', 'Renovaciones'], ['ingresos', 'Ingresos'], ['reportes', 'Reportes'],
  ['no_renovados', 'No renovados'], ['equipo', 'Equipo'], ['catalogos', 'Catálogos'], ['bitacora', 'Bitácora']]

export default function AdminPanel() {
  const { user, logout } = useAuth()
  const [vista, setVista] = useState<Vista>('cartera')
  const [abrir, setAbrir] = useState<{ id: number; paquete: number | null } | null>(null)
  const [refrescoCms, setRefrescoCms] = useState(0)
  const [cmTablero, setCmTablero] = useState('')
  const [cms, setCms] = useState<UsuarioEquipo[]>([])
  useEffect(() => { api.get<UsuarioEquipo[]>('/usuarios').then((u) => setCms(u.filter((x) => x.rol === 'cm' && x.activo))) }, [refrescoCms])

  const irACliente = (id: number, paquete: number | null = null) => { setAbrir({ id, paquete }); setVista('cartera') }
  return (
    <div className="cm-layout">
      <aside className="cm-sidebar">
        <div className="cm-sidebar-header">
          <div style={{ flexShrink: 0 }}><Logo size={34} /></div>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.nombre}</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)' }}>Panel admin{user?.solo_lectura ? ' · solo lectura' : ''}</div>
          </div>
          <NotificationBell onAbrirPaquete={(c, p) => irACliente(c, p)} />
        </div>
        <div className="cm-sidebar-list">
          {NAV.map(([k, t]) => <button key={k} className={`cm-sidebar-item ${vista === k ? 'active' : ''}`} onClick={() => { setVista(k); if (k === 'cartera') setAbrir(null) }}>{t}</button>)}
        </div>
        <button className="btn btn-ghost-dark" style={{ marginTop: 10 }} onClick={logout}>Cerrar sesión</button>
      </aside>
      <main className="cm-main">
        {vista === 'cartera' && <CarteraView abrirId={abrir?.id ?? null} abrirPaquete={abrir?.paquete ?? null} cmsRefresco={refrescoCms} />}
        {vista === 'renovaciones' && (
          <div>
            <div className="field" style={{ maxWidth: 240 }}><label>CM</label>
              <select value={cmTablero} onChange={(e) => setCmTablero(e.target.value)}><option value="">Todos los CM</option>{cms.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></div>
            <Tablero cmId={cmTablero ? Number(cmTablero) : null} mostrarCm onAbrir={(c, p) => irACliente(c, p)} />
          </div>)}
        {vista === 'ingresos' && <Ingresos onAbrirCliente={(id) => irACliente(id)} />}
        {vista === 'reportes' && <Reportes />}
        {vista === 'no_renovados' && <NoRenovados onAbrir={(id) => irACliente(id)} onCambio={() => setRefrescoCms((n) => n + 1)} />}
        {vista === 'equipo' && <EquipoView onCambio={() => setRefrescoCms((n) => n + 1)} />}
        {vista === 'catalogos' && <CatalogosView />}
        {vista === 'bitacora' && <BitacoraView />}
      </main>
    </div>
  )
}
