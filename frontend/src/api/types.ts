export interface Usuario {
  id: number; nombre: string; username: string; rol: 'cm' | 'admin'; solo_lectura: boolean; activo: boolean
}
export interface LoginResponse { access_token: string; usuario: Usuario }

export type Semaforo = 'verde' | 'amarillo' | 'rojo' | 'gris'
export type EstadoPaquete = 'activo' | 'por_vencer' | 'vencido' | 'renovado' | 'archivado' | 'eliminado'

export interface Paquete {
  id: number; cliente_id: number; paquete_id: number; paquete: string; tipo_id: number; tipo: string
  costo: number; pagado: number; restante: number; avance_pct: number
  fecha_inicio: string; fecha_renovacion: string; quincena: 1 | 2; dias_para_renovar: number
  estado: string; estado_efectivo: EstadoPaquete
  renovacion_decision: 'pendiente' | 'si' | 'no'; renovacion_pagada: boolean; semaforo: Semaforo
  prorroga_hasta: string | null; prorroga_registrada_en: string | null; prorroga_dias_restantes: number | null
  prorroga_activa: boolean; prorroga_vencida: boolean
  bloqueado: boolean; opciones_bloqueo: ('renovo' | 'no_renovo' | 'prorroga')[]; limite_decision: string | null
  no_renovara: boolean
  ciclo_anterior_id: number | null; archivado_en: string | null
}
export interface Pago {
  id: number; monto: number; fecha: string; nota: string | null; registrado_por: number
  registrado_por_nombre: string | null; creado_en: string
}
export interface Bloqueo extends Paquete { cliente_nombre: string; cm_id: number | null }
export interface PaqueteDetalle extends Paquete {
  veces_renovado: number; pagos: Pago[]; ciclos: Paquete[]
  renovaciones: { id: number; fecha: string; costo_anterior: number; costo_nuevo: number
    paquete_anterior_id: number; paquete_nuevo_id: number; ciclo_anterior_id: number; ciclo_nuevo_id: number }[]
}

export interface ClienteListItem {
  id: number; nombre: string; estado: 'activo' | 'no_renovado'; cm_id: number | null; cm_nombre: string | null
  telefono: string | null; paquetes_vigentes: number; semaforo: Semaforo | null; quincenas: number[]
  proxima_renovacion: string | null
}
export interface ClienteFicha {
  id: number; nombre: string; estado: 'activo' | 'no_renovado'; cm_id: number | null
  correo_fb: string | null; tiene_password_fb: boolean; correo_contacto: string | null
  telefono: string | null; observaciones: string | null
  paquetes: Paquete[]; historial: Paquete[]; no_renovado_desde: string | null
}
export interface CatalogoItem { id: number; nombre: string; orden: number; activo: boolean }

export interface Recordatorio {
  id: number; paquete_id: number; texto: string; wa_url: string | null; telefono: string | null
  generado_en: string; enviado_en: string | null
}
export interface Notificacion {
  id: number; tipo: string; mensaje: string; cliente_id: number | null; paquete_id: number | null
  requiere_respuesta: boolean; respuesta: 'si' | 'no' | null; respondida_en: string | null; leida: boolean; creado_en: string
}
export interface NotificacionesResp { no_leidas: number; preguntas_pendientes: number; items: Notificacion[] }

export interface TarjetaTablero extends Paquete {
  cliente_nombre: string; cm_id: number | null; cm_nombre: string | null; arrastrado: boolean
}
export interface Tablero {
  periodo: { anio: number; mes: number; quincena: string; desde: string; hasta: string; etiqueta: string }
  columnas: { por_vencer: TarjetaTablero[]; vencidos: TarjetaTablero[]; renovados_sin_pago: TarjetaTablero[]; completos: TarjetaTablero[] }
  en_plazo: number
}

export interface PeriodoInfo {
  anio: number; mes: number; quincena: string; desde: string; hasta: string; corte: string; cerrado: boolean
  etiqueta: string; estado_texto: string
}
export interface Totales { proyeccion: number; cobrado: number; pendiente: number; pct_cobrado: number; clientes: number; paquetes: number }
export interface FilaCM {
  cm_id: number | null; cm: string; clientes: number; paquetes: number; proyeccion: number; cobrado: number
  pendiente: number; pct_cobrado: number
}
export interface FilaTasa { cm_id: number | null; cm: string; vencidos: number; renovados: number; tasa: number }
export interface IngresosResp {
  periodo: PeriodoInfo; totales: Totales
  clientes: { cliente_id: number; cliente: string; cm: string; paquetes: number; proyeccion: number; actual: number; pendiente: number; pct_cobrado: number }[]
  por_cm?: FilaCM[]; total_general?: FilaCM; tasa_renovacion?: FilaTasa[]
  tasa_total: { vencidos: number; renovados: number; tasa: number }
}
export interface FilaDetalle {
  paquete_id: number; cliente_id: number; cm_id: number | null; cm: string; cliente: string; paquete: string; tipo: string
  costo: number; pagado: number; restante: number; fecha_renovacion: string; estado: string; estado_efectivo: EstadoPaquete
  semaforo: Semaforo; decision: string
}
export interface ReporteDatos {
  periodo: PeriodoInfo; resumen: Totales; por_cm: FilaCM[]; total_cm: FilaCM; detalle: FilaDetalle[]
  prorrogas: { cm: string; cliente: string; paquete: string; tipo: string; costo: number; pagado: number; restante: number
    fecha_limite: string; dias: number; vencida: boolean }[]
  pendientes: Record<'por_vencer' | 'vencidos' | 'renovados_sin_pago', { cm: string; items: FilaDetalle[] }[]>
  tasa_renovacion: FilaTasa[]; tasa_total: { vencidos: number; renovados: number; tasa: number }; alcance: string
}

export interface UsuarioEquipo extends Usuario { creado_en: string; clientes_activos: number; clientes_no_renovados: number }
export interface BitacoraItem { id: number; usuario: string; accion: string; detalle: Record<string, unknown> | null; creado_en: string }
