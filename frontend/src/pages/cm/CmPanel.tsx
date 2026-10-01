import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { ClienteListItem } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import BloqueoModal from '../../components/BloqueoModal'
import Logo from '../../components/Logo'
import NotificationBell from '../../components/NotificationBell'
import { Semaforo } from '../../components/ui'
import { quincenaActual } from '../../util'
import ClienteFicha from '../shared/ClienteFicha'
import Ingresos from '../shared/Ingresos'
import { AgregarClienteModal } from '../shared/modales'
import NoRenovados from '../shared/NoRenovados'
import Reportes from '../shared/Reportes'
import Tablero from '../shared/Tablero'

type Vista = { tipo: 'inicio' } | { tipo: 'cliente'; id: number; paquete: number | null } | { tipo: 'tablero' } | { tipo: 'ingresos' } | { tipo: 'no_renovados' } | { tipo: 'reportes' }

export default function CmPanel() {
  const { user, logout } = useAuth()
  const [quincena, setQuincena] = useState<'1' | '2'>(quincenaActual())
  const [clientes, setClientes] = useState<ClienteListItem[]>([])
  const [vista, setVista] = useState<Vista>({ tipo: 'tablero' })
  const [agregando, setAgregando] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [version, setVersion] = useState(0)          // se incrementa al resolver un bloqueo para recargar la vista actual

  const cargar = useCallback(() => api.get<ClienteListItem[]>(`/clientes?quincena=${quincena}`).then(setClientes), [quincena])
  useEffect(() => { cargar() }, [cargar])

  const abrir = (id: number, paquete: number | null = null) => setVista({ tipo: 'cliente', id, paquete })
  const visibles = clientes.filter((c) => c.nombre.toLowerCase().includes(busqueda.toLowerCase()))

  return (
    <div className="cm-layout">
      <aside className="cm-sidebar">
        <div className="cm-sidebar-header">
          <div style={{ flexShrink: 0 }}><Logo size={34} /></div>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.nombre}</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)' }}>Panel CM</div>
          </div>
          <NotificationBell onAbrirPaquete={(c, p) => abrir(c, p)} />
        </div>

        <div className="segmented full" style={{ marginBottom: 10 }} role="tablist" aria-label="Quincena">
          <button className={quincena === '1' ? 'active' : ''} onClick={() => setQuincena('1')}>1ra quincena</button>
          <button className={quincena === '2' ? 'active' : ''} onClick={() => setQuincena('2')}>2da quincena</button>
        </div>
        <button className="btn btn-primary" onClick={() => setAgregando(true)} style={{ marginBottom: 10, justifyContent: 'center' }}>+ Agregar cliente</button>
        <input type="text" placeholder="Buscar cliente…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
          style={{ marginBottom: 8, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', color: 'white' }} />

        <div className="cm-sidebar-list">
          {visibles.length === 0 && <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, padding: '4px 8px' }}>
            {clientes.length === 0 ? 'Sin clientes con renovación en esta quincena.' : 'Sin resultados.'}</p>}
          {visibles.map((c) => (
            <button key={c.id} className={`cm-sidebar-item ${vista.tipo === 'cliente' && vista.id === c.id ? 'active' : ''}`} onClick={() => abrir(c.id)}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.nombre}</span>
              <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                {c.quincenas.length === 2 && <span className="badge badge-neutral" title="Tiene paquetes en ambas quincenas" style={{ padding: '0 6px' }}>1·2</span>}
                <Semaforo valor={c.semaforo} /></span>
            </button>))}
        </div>

        <div className="cm-sidebar-nav">
          {([['tablero', 'Renovaciones'], ['ingresos', 'Ingresos'], ['reportes', 'Reportes'], ['no_renovados', 'No renovados']] as const).map(([k, t]) => (
            <button key={k} className={`cm-sidebar-item ${vista.tipo === k ? 'active' : ''}`} onClick={() => setVista({ tipo: k })}>{t}</button>))}
          <button className="btn btn-ghost-dark" style={{ marginTop: 6 }} onClick={logout}>Cerrar sesión</button>
        </div>
      </aside>

      <main className="cm-main">
        {vista.tipo === 'cliente' && <ClienteFicha key={`${vista.id}-${version}`} clienteId={vista.id} paqueteInicial={vista.paquete} onChanged={cargar}
          onDeleted={() => { cargar(); setVista({ tipo: 'tablero' }) }} />}
        {vista.tipo === 'tablero' && <Tablero key={version} onAbrir={(c, p) => abrir(c, p)} />}
        {vista.tipo === 'ingresos' && <Ingresos key={version} onAbrirCliente={(id) => abrir(id)} />}
        {vista.tipo === 'reportes' && <Reportes />}
        {vista.tipo === 'no_renovados' && <NoRenovados key={version} onAbrir={(id) => abrir(id)} onCambio={cargar} />}
      </main>

      <BloqueoModal onResuelto={() => { cargar(); setVersion((n) => n + 1) }} />
      {agregando && <AgregarClienteModal onClose={() => setAgregando(false)} onHecho={(id) => { setAgregando(false); cargar(); abrir(id) }} />}
    </div>
  )
}
