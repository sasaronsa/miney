# Miney

Aplicación de finanzas personales **autohospedada y de un solo usuario**: control de ahorro, gastos por categoría, suscripciones con detección de subidas de precio, presupuestos e importación masiva de extractos bancarios (CSV/Excel/PDF) con deduplicación. Interfaz moderna tipo fintech, instalable como PWA en el móvil (iOS/Android).

Pensada para correr en una Raspberry Pi con **Home Assistant OS** (como add-on) o en cualquier servidor con **Docker Compose**, idealmente detrás de un Cloudflare Tunnel + Cloudflare Access.

## Funcionalidades

- **Cuentas** (corriente, ahorro, efectivo, tarjeta) con evolución de saldo
- **Importación masiva** de extractos: CSV/Excel con mapeo de columnas configurable y plantillas reutilizables por banco, PDF con texto seleccionable. Vista previa con deduplicación (por ID de transacción o por hash de contenido), detección de **transferencias internas** entre tus cuentas (no cuentan como gasto/ingreso) y opción de **deshacer una importación** completa
- **Categorías jerárquicas** con reglas de auto-categorización editables, revisión rápida en lote y **división de un cargo en varias categorías**
- **Suscripciones**: detección automática de pagos recurrentes, avisos de subida/bajada de precio, fechas de alta/baja, próximo cargo estimado y gráfico de evolución del precio
- **Presupuestos** mensuales recurrentes (con vigencia indefinida o acotada) y por rango de fechas
- **Dashboard** con evolución del patrimonio, cashflow mensual, gasto por categoría, top comercios y % de ahorro
- **Búsqueda global**, exportación CSV/JSON, **modo demo** (difumina todas las cifras para enseñar la app) y **PWA** instalable

## Stack

FastAPI + SQLModel + Alembic · SQLite (fichero único en volumen persistente) · Jinja2 + HTMX + Alpine.js + Tailwind (sin build de frontend) · Chart.js. Un solo contenedor, ~sin dependencias externas.

---

## Opción A · Add-on de Home Assistant OS

1. En Home Assistant: **Ajustes → Complementos → Tienda de complementos → ⋮ → Repositorios** y añade:
   ```
   https://github.com/<tu-usuario>/miney
   ```
2. Instala el add-on **Miney** que aparecerá en la tienda (compila la imagen en local; en una Raspberry Pi tarda unos minutos la primera vez).
3. En la pestaña **Configuración** del add-on define `username` y `password` (el resto es opcional) y guárdala.
4. **Inicia** el add-on. Las migraciones de base de datos se aplican solas en cada arranque; los datos viven en `/data` del add-on y sobreviven a actualizaciones y rebuilds.
5. La web queda en `http://<ip-de-home-assistant>:8010` (puerto configurable en la pestaña Configuración → Red).

> El puerto por defecto del add-on es **8010** para no chocar con otros add-ons que usen el 8000.

Para exponerla fuera de casa, apunta tu Cloudflare Tunnel a ese puerto y protégela con Cloudflare Access; el login propio de la app queda como segunda capa.

## Opción B · Docker Compose (cualquier servidor)

```bash
git clone https://github.com/<tu-usuario>/miney
cd miney
cp .env.example .env
# edita .env: APP_USERNAME y APP_PASSWORD (2 líneas y listo)
docker compose up -d --build
```

Abre `http://localhost:8000`. La base de datos y los ficheros persisten en el volumen `miney_data`.

### Configuración

| Variable | Descripción | Por defecto |
|---|---|---|
| `APP_USERNAME` | Usuario de login | `admin` |
| `APP_PASSWORD` | Contraseña en claro; se hashea con bcrypt al arrancar | — |
| `APP_PASSWORD_HASH_B64` | (Avanzado) hash bcrypt en base64; prioridad sobre `APP_PASSWORD` | — |
| `SECRET_KEY` | Firma de la cookie de sesión; si está vacía se autogenera y persiste en `<DATA_DIR>/secret_key` | autogenerada |
| `APP_NAME` | Nombre visible | `Miney` |
| `DEFAULT_CURRENCY` | Moneda | `EUR` |
| `DATABASE_URL` | Cadena SQLAlchemy | `sqlite:////data/miney.db` (Docker) |
| `DATA_DIR` / `UPLOAD_DIR` | Datos persistentes y subidas temporales | `/data` · `/data/uploads` (Docker) |

### Datos de ejemplo

Para probar la app sin subir un extracto real:

```bash
docker compose exec miney python -m app.seed        # Docker Compose
docker exec addon_miney python -m app.seed          # Add-on de HA (nombre según slug)
```

### Backup

Todo vive en un único fichero SQLite:

```bash
docker compose exec miney sqlite3 /data/miney.db ".backup /data/backup.db"
docker cp miney:/data/backup.db ./backup-$(date +%F).db
```

También puedes exportar movimientos a CSV/JSON desde la propia app (`/export`).

### Actualizar

- **Add-on**: sube los cambios a GitHub, y en HA usa "Buscar actualizaciones" / reconstruir. Las migraciones se aplican solas al arrancar.
- **Compose**: `git pull && docker compose up -d --build`.

---

## Desarrollo local

Requiere Python 3.12+.

```bash
python -m venv .venv && .venv/Scripts/activate    # Windows (source .venv/bin/activate en Linux/Mac)
pip install -r requirements.txt
cp .env.example .env
# en .env: APP_PASSWORD=lo-que-sea y DATABASE_URL=sqlite:///./data/misfinanzas_dev.db
alembic upgrade head
python -m app.seed          # opcional
uvicorn app.main:app --reload
```

## Instalar como app en el móvil (PWA)

Sirve la app por **HTTPS** (Cloudflare Tunnel lo da gratis), ábrela en Safari (iOS) o Chrome (Android) y usa **"Añadir a pantalla de inicio"**. Se instala con su icono y se abre a pantalla completa, con soporte de notch/Dynamic Island y caché offline básica.

## Estructura del proyecto

```
app/
  models/       # SQLModel: Account, Transaction(+Split), Category, Rule, Subscription, Budget, ImportBatch, MappingTemplate
  routers/      # Un módulo por sección (dashboard, accounts, transactions, subscriptions, budgets, imports, rules, search, export)
  services/     # Lógica: importación (parsers/mapeo/dedup/transferencias), categorización, recurrentes, estadísticas
  templates/    # Vistas Jinja2 (HTMX + Alpine + Tailwind vía CDN)
  static/       # PWA: manifest, service worker, iconos
alembic/        # Migraciones (se aplican automáticamente al arrancar el contenedor)
config.yaml     # Definición del add-on de Home Assistant
repository.yaml # Repositorio de add-ons de HA (añadir esta URL en la tienda)
entrypoint.py   # Entrypoint común Docker/HA: options.json → env, migraciones, uvicorn
```

## Notas de seguridad

- Un solo usuario; sesión con cookie firmada y contraseña bcrypt.
- Diseñada para ir **detrás de Cloudflare Access** (o un proxy con autenticación) si la expones a internet; el login propio es la segunda capa, no la única.
- El modo demo es visual (CSS): oculta cifras en pantalla para enseñar la app, no protege los datos frente a alguien con acceso a la sesión.

## Licencia

[MIT](LICENSE)
