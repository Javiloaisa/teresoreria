# Teresorería

App personal de control de gastos. Se apunta cada gasto a mano, se reparte en
tres botes con la regla **50-30-20** y la app avisa **antes** de pasarse, no
después.

- **Frontend:** React + Vite + TypeScript + Tailwind v4 (PWA instalable en el móvil)
- **Backend:** FastAPI + PostgreSQL
- **Despliegue:** VPS de Hetzner, stack Docker propio detrás del Caddy compartido

Estado: **F1, F2 y F3 hechas** (botes, gastos, recurrentes con prorrateo, reglas
de clasificación, y avisos push con su repaso diario). Pendiente F4 (historial y
comparativa entre meses).

---

## La idea

Tres botes calculados sobre el ingreso neto del mes:

| Bote | Por defecto |
|---|---|
| Necesidades | 50 % |
| Deseos | 30 % |
| Ahorro | 20 % |

Los porcentajes se cambian en Ajustes (algún mes puede interesar 60-20-20).

La **base** de cálculo tiene dos modos: `fijo` (un ingreso base declarado) o
`real` (la suma de lo ingresado este mes). En modo real, mientras no haya
ingresos registrados se usa la media de los meses anteriores y la pantalla lo
marca como **estimada** en vez de fingir certeza.

## El prorrateo, que es lo que hace que la app sirva

Un seguro de coche de 480 € al año **no se imputa entero al mes del cargo**: se
reservan 40 € cada mes, y esa reserva descuenta del bote desde el día 1.

```
reserva_mensual = importe / meses_del_periodo
```

Cuando llega el cargo real se registra como gasto con su `recurrente_id`, y
entonces **no cuenta para el ritmo ni mueve la barra**: ese dinero ya estaba
apartado. Sin esto, todos los meses con cargos anuales aparecerían en rojo, se
dejarían de mirar los avisos y la app moriría. Es el caso que blinda
[`tests/test_calc.py`](tests/test_calc.py) (`test_el_cargo_real_no_mueve_la_barra`).

## Proyección y estado

Para cada bote, el día D de un mes de N días:

```
presupuesto      = base × pct / 100
reservas         = suma de reservas mensuales de los recurrentes de ese bote
variable_gastado = gastos del mes de ese bote SIN recurrente_id
proyeccion       = reservas + (variable_gastado / D) × N
```

- **Verde** — `proyeccion <= presupuesto × umbral`
- **Ámbar** — la proyección pasa el umbral pero no el presupuesto
- **Rojo** — la proyección se pasa, o ya te has pasado de hecho

Los primeros 5 días del mes el estado se pinta pero no se notifica: con tres
días de datos la proyección es ruido.

## Avisos

Un repaso diario a la hora que diga `config.hora_aviso` (por defecto las 08:30),
con APScheduler dentro del propio proceso de la API. Por eso uvicorn corre con
**un solo worker**: con varios, cada aviso saldría repetido.

El antispam es la parte delicada, porque un aviso que se repite deja de leerse:
**uno por bote, nivel y mes**, garantizado por el índice único de
`avisos_enviados`. Un bote que vuelve a verde pierde sus filas, así que si se
tuerce otra vez en el mismo mes vuelve a avisar. De ámbar a rojo sí se avisa
(empeorar es noticia); de rojo a ámbar no.

Un aviso solo se da por enviado si de verdad llegó a algún dispositivo. Si
todavía no hay ninguno suscrito, mañana se reintenta en vez de perderse.

```
Deseos: te vas a pasar
Vas camino de 340 € y el tope son 300 €. Quedan 11 días.
```

Las suscripciones que el navegador tira (desinstalar la app, borrar los datos
del sitio) se borran solas al recibir un 404 o 410 del servicio de push.

## Clasificación automática

Al escribir el concepto se normaliza (minúsculas, sin acentos) y se busca la
primera regla que case, ordenando por prioridad y luego por usos. La categoría
queda preseleccionada y el usuario siempre puede cambiarla; al cambiarla, la app
ofrece guardar la regla para la próxima vez.

El patrón casa como subcadena **pero la palabra tiene que acabar donde acaba el
patrón** (o seguir con la 's' del plural). Sin eso, la regla `bar` mandaría a
Deseos la «Ferretería del barrio» y cualquier compra en Barcelona. Con el plural
permitido, `seguro` sigue reconociendo «SEGUROS MAPFRE».

Sin IA a propósito: con 30 o 40 reglas queda cubierto el grueso del gasto real y
el comportamiento es predecible, que es lo que se quiere en una herramienta de
números.

---

## Estructura

| Fichero | Qué hace |
|---|---|
| [schema.sql](schema.sql) | Esquema completo y reglas de arranque. Lo carga Postgres en el primer arranque |
| [api/calc.py](api/calc.py) | ⭐ Prorrateo, botes, proyección y estado. Lógica pura, sin SQL ni HTTP |
| [api/clasificar.py](api/clasificar.py) | ⭐ Normalización y coincidencia de reglas. También pura |
| [api/index.py](api/index.py) | Rutas de FastAPI, todas bajo `/api` |
| [api/auth.py](api/auth.py) | Contraseña con argon2 y cookie de sesión firmada (60 días) |
| [api/db.py](api/db.py) | Pool de conexiones a Postgres |
| [api/avisos.py](api/avisos.py) | ⭐ Qué avisar, con qué texto y el antispam. También pura |
| [api/push.py](api/push.py) | Envío por Web Push (VAPID) con pywebpush |
| [api/manage.py](api/manage.py) | `set-password`: crea o cambia la contraseña |
| [api/gen_vapid.py](api/gen_vapid.py) | Genera el par de claves VAPID (una sola vez) |
| [frontend/src/](frontend/src/) | Las tres pantallas: Resumen, Añadir gasto y Ajustes |
| [scripts/gen_iconos.py](scripts/gen_iconos.py) | Genera los PNG de la PWA (solo si se cambia el diseño) |
| [tests/](tests/) | pytest. Los de `calc` y `clasificar` no necesitan base de datos |

`frontend/src/clasificar.ts` es una **copia en TypeScript** de `clasificar.py`:
preseleccionar la categoría mientras se escribe tiene que ser instantáneo y una
petición por tecla no lo es. Si se cambia la forma de casar, hay que cambiarla
en los dos sitios; la de Python es la de referencia y la que tiene los tests.

---

## Desarrollo en local

La base de datos de desarrollo vive en el Postgres del propio VPS, así que no
hace falta instalar Postgres ni Docker en local. En tres terminales:

```bash
# 1) Túnel a la base de datos de desarrollo
ssh -i ~/.ssh/hetzner_deploy -L 55432:127.0.0.1:5432 root@178.104.99.197 -N

# 2) API (lee el .env de la raíz)
cd api && ../.venv/Scripts/uvicorn index:app --reload --port 8000

# 3) Frontend (Vite manda /api al puerto 8000)
cd frontend && npm run dev
```

El `.env` de local necesita `DATABASE_URL` apuntando al túnel, `SECRET_KEY` y
`COOKIE_SECURE=0` (en local no hay HTTPS). Ver [.env.example](.env.example).

```bash
pytest tests/ -q          # los de calc y clasificar van sin base de datos
```

⚠️ `tests/test_api.py` **vacía** las tablas de gastos, ingresos y recurrentes:
apunta siempre a la base de desarrollo, nunca a producción.

---

## Despliegue

Automático al hacer push a `main`
([.github/workflows/deploy.yml](.github/workflows/deploy.yml)):

```
git push origin main
   └─► CI: pytest + build del frontend ──(verde)──► rsync a /opt/teresoreria
                                                      └─► docker compose up -d --build
```

El stack son tres contenedores (`db`, `api`, `caddy`) aislados en
`/opt/teresoreria`. Su Caddy **no** toma los puertos 80/443: los tiene el Caddy
frontal de `/opt/partes-de-obra`, que enruta por nombre de host:

```
teresoreria-178-104-99-197.sslip.io  →  host.docker.internal:8091
```

El `rsync` usa `--delete` pero excluye `.env` y los `backup_*.sql`, así que los
secretos y las copias del servidor sobreviven a cada despliegue.

Mientras el workflow no esté subido (necesita el permiso `workflow` en el token
de `gh`), el despliegue se hace a mano por SSH, que es como se hizo el primero:

```bash
ssh root@178.104.99.197
cd /opt/teresoreria && git pull && docker compose up -d --build
```

Primera vez en el servidor:

```bash
cd /opt/teresoreria
cp .env.example .env && nano .env      # DB_PASSWORD, SECRET_KEY, COOKIE_SECURE=1
docker compose up -d --build
docker compose exec api python manage.py set-password

# Claves para los avisos push (una sola vez); pega las dos lineas en el .env
docker compose exec api python gen_vapid.py
docker compose up -d api
```

## En el móvil

Abrir `https://teresoreria-178-104-99-197.sslip.io` y **Compartir → Añadir a
pantalla de inicio**. En iPhone ese paso no es opcional para los avisos de F3:
Apple solo entrega notificaciones web a las apps instaladas (iOS 16.4 o
superior), y sin instalar la suscripción falla sin explicar por qué. La app lo
detecta y lo avisa en Ajustes en vez de dejarte con un botón que no funciona.

Una vez instalada: Ajustes → Avisos en el móvil → **Activar los avisos**, y
comprueba que llegan con **Enviarme un aviso de prueba** antes de fiarte.
