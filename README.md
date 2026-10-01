# Control de clientes y paquetes (INNquietus)

Sistema web para llevar clientes, paquetes, pagos, prórrogas y renovaciones de la agencia, con panel para CM y para admin.

## Probarlo en tu computadora

Solo necesitas **Docker**. Sin crear archivos, sin configurar nada:

```bash
git clone https://github.com/kirito203278/control-clientes.git
cd control-clientes
docker compose -f docker-compose.demo.yml up --build
```

La primera vez tarda unos minutos (compila la interfaz). Cuando veas `Uvicorn running`, abre **http://localhost:8000**.
Se crean solas las tablas y unos datos de ejemplo (clientes ficticios).

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin.demo` | `Admin-Demo-2026` | administrador |
| `lectura.demo` | `Lectura-Demo-2026` | administrador de solo lectura |
| `ana.ruiz` | `Ana-Demo-2026` | CM |
| `beto.luna` | `Beto-Demo-2026` | CM |
| `carla.soto` | `Carla-Demo-2026` | CM |

Los datos de ejemplo son 31 clientes ficticios (10 por CM y 1 por reasignar), con meses de historial para que los reportes y los ingresos tengan qué mostrar. Hay uno de cada situación:

- **Ventana de decisión (contrato terminado):** Gimnasio FuerzaMX (aún no contesta), Dentista Sonríe (ya pagó), Boutique Aurora (confirmó y no pagó: toca prórroga).
- **Prórroga corriendo:** Café Tlalli y Abarrotes La Esquina.
- **Confirmó que renovará:** Taquería Los Compadres (y pidió cambiar de paquete) y Estética Bella Vista.
- **Marcado «no renovará»:** Pastelería Dulce Hogar y Florería Jazmín.
- **Por vencer (aviso a 4 días):** Dra. Mariana Vélez y Óptica Visión Clara.
- **No renovados:** 6 clientes con distinta antigüedad. Imprenta Central trae su mensaje de cobro listo para enviar.
- **Por reasignar:** Escuela de Baile Ritmo (entra como admin).

Las notificaciones, la bitácora y el historial de renovaciones también vienen con datos.

Para apagarlo: `Ctrl+C`. Para borrar los datos y empezar limpio: `docker compose -f docker-compose.demo.yml down -v`. Los datos de ejemplo se cargan solo cuando la base está vacía: si ya la habías levantado antes, usa ese comando para recibir los datos nuevos.

> Las claves de este modo son de ejemplo y solo sirven en tu computadora. No lo uses para producción.

## Sin Docker

```bash
./scripts/probar_sin_docker.sh
```

Necesita `python3` y `node`/`npm`. Levanta un Postgres temporal y la app en http://localhost:8000.

## Más información

- [COMO_EJECUTAR.md](COMO_EJECUTAR.md): desarrollo con recarga en vivo y pruebas automáticas.
- [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md): publicarlo en Render + Neon.
- [ESTADO.md](ESTADO.md): reglas de negocio y decisiones tomadas.
