-- Teresorería — esquema completo.
--
-- Este fichero lo ejecuta Postgres UNA SOLA VEZ, en el primer arranque con la
-- base de datos vacía (va montado en /docker-entrypoint-initdb.d). Para cambios
-- posteriores hay que escribir migraciones aparte, no tocar esto.

CREATE TYPE categoria     AS ENUM ('necesidad', 'deseo', 'ahorro');
CREATE TYPE periodicidad  AS ENUM ('mensual', 'bimestral', 'trimestral', 'semestral', 'anual');


-- Un solo usuario: la fila 1 y nada más (de ahí el CHECK). Se crea con
--   docker compose exec api python manage.py set-password
-- No hay registro, ni recuperación, ni roles.
CREATE TABLE usuario (
  id             SMALLINT PRIMARY KEY DEFAULT 1,
  password_hash  TEXT NOT NULL,
  CHECK (id = 1)
);


CREATE TABLE ingresos (
  id        SERIAL PRIMARY KEY,
  fecha     DATE NOT NULL,
  concepto  TEXT NOT NULL,
  importe   NUMERIC(10,2) NOT NULL,
  tipo      TEXT NOT NULL DEFAULT 'otro'    -- 'nomina' | 'factura' | 'otro'
);

CREATE INDEX ingresos_fecha_idx ON ingresos (fecha);


-- Gastos que se repiten. `importe` es el del CARGO COMPLETO (los 480 € del
-- seguro anual), no la reserva mensual: esa se calcula al vuelo en calc.py
-- dividiendo entre los meses del periodo.
CREATE TABLE recurrentes (
  id            SERIAL PRIMARY KEY,
  concepto      TEXT NOT NULL,
  importe       NUMERIC(10,2) NOT NULL,
  periodicidad  periodicidad NOT NULL,
  mes_cargo     SMALLINT,      -- 1-12, solo si no es mensual
  dia_cargo     SMALLINT,
  cat           categoria NOT NULL,
  activo        BOOLEAN NOT NULL DEFAULT TRUE,
  CHECK (mes_cargo IS NULL OR mes_cargo BETWEEN 1 AND 12),
  -- Tope 28 a propósito: un cargo el día 30 se perdería en febrero.
  CHECK (dia_cargo IS NULL OR dia_cargo BETWEEN 1 AND 28)
);


-- Reglas de clasificación automática. `patron` se guarda YA NORMALIZADO
-- (minúsculas y sin acentos, ver clasificar.py) para poder comparar directo.
CREATE TABLE reglas (
  id         SERIAL PRIMARY KEY,
  patron     TEXT NOT NULL,
  cat        categoria NOT NULL,
  prioridad  SMALLINT NOT NULL DEFAULT 0,
  usos       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX reglas_orden_idx ON reglas (prioridad DESC, usos DESC);


CREATE TABLE gastos (
  id             SERIAL PRIMARY KEY,
  fecha          DATE NOT NULL DEFAULT CURRENT_DATE,
  concepto       TEXT NOT NULL,
  importe        NUMERIC(10,2) NOT NULL,
  cat            categoria NOT NULL,
  -- NULL = gasto variable. Con valor = es el cargo de un recurrente, y entonces
  -- NO cuenta para el ritmo ni para la barra: ya estaba apartado en la reserva.
  recurrente_id  INTEGER REFERENCES recurrentes(id) ON DELETE SET NULL,
  regla_id       INTEGER REFERENCES reglas(id) ON DELETE SET NULL,
  nota           TEXT
);

CREATE INDEX gastos_fecha_idx ON gastos (fecha DESC);
CREATE INDEX gastos_cat_idx   ON gastos (cat);


CREATE TABLE config (
  id                SMALLINT PRIMARY KEY DEFAULT 1,
  base_mode         TEXT NOT NULL DEFAULT 'real',   -- 'fijo' | 'real'
  ingreso_base      NUMERIC(10,2),
  pct_necesidades   SMALLINT NOT NULL DEFAULT 50,
  pct_deseos        SMALLINT NOT NULL DEFAULT 30,
  pct_ahorro        SMALLINT NOT NULL DEFAULT 20,
  umbral_amarillo   NUMERIC(3,2) NOT NULL DEFAULT 0.90,
  hora_aviso        TIME NOT NULL DEFAULT '08:30',
  CHECK (id = 1),
  CHECK (base_mode IN ('fijo', 'real')),
  CHECK (pct_necesidades + pct_deseos + pct_ahorro = 100)
);

INSERT INTO config (id) VALUES (1);


-- ── Notificaciones push ──────────────────────────────────────────────────────
-- Se crean ya aunque F3 (cron y avisos) todavía no esté hecho: así esa fase no
-- tiene que tocar el esquema de una base con datos reales dentro.

CREATE TABLE push_subscriptions (
  id          SERIAL PRIMARY KEY,
  endpoint    TEXT NOT NULL UNIQUE,
  p256dh      TEXT NOT NULL,
  auth        TEXT NOT NULL,
  user_agent  TEXT,
  creada      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- El índice único es el antispam: un aviso por bote, nivel y mes. Si el estado
-- baja a verde y vuelve a subir, se borra la fila y el aviso se rearma.
CREATE TABLE avisos_enviados (
  id       SERIAL PRIMARY KEY,
  mes      DATE NOT NULL,              -- primer día del mes
  cat      categoria NOT NULL,
  nivel    TEXT NOT NULL,              -- 'amarillo' | 'rojo'
  enviado  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (mes, cat, nivel)
);


-- ── Reglas de arranque ───────────────────────────────────────────────────────
-- Un puñado de patrones del gasto corriente en España para que la app clasifique
-- algo desde el primer día. Se editan y se amplían desde Ajustes; la app aprende
-- sola cada vez que se corrige la categoría de un gasto.
--
-- El patrón casa como subcadena, pero la palabra tiene que acabar donde acaba
-- el patrón (o seguir con la 's' del plural). Ver `casa()` en clasificar.py:
-- por eso 'bar' reconoce "BAR MANOLO" y no la "Ferretería del barrio".

INSERT INTO reglas (patron, cat, prioridad) VALUES
  ('mercadona',   'necesidad', 10),
  ('lidl',        'necesidad', 10),
  ('carrefour',   'necesidad', 10),
  ('consum',      'necesidad', 10),
  ('alquiler',    'necesidad', 20),
  ('hipoteca',    'necesidad', 20),
  ('luz',         'necesidad', 10),
  ('agua',        'necesidad', 10),
  ('gas',         'necesidad', 10),
  ('internet',    'necesidad', 10),
  ('farmacia',    'necesidad', 10),
  ('gasolina',    'necesidad', 10),
  ('seguro',      'necesidad', 10),
  ('bar',         'deseo',      5),
  ('cafeteria',   'deseo',     10),
  ('restaurante', 'deseo',     10),
  ('amazon',      'deseo',     10),
  ('netflix',     'deseo',     10),
  ('spotify',     'deseo',     10),
  ('cine',        'deseo',     10),
  ('ahorro',      'ahorro',    20),
  ('inversion',   'ahorro',    20),
  ('fondo',       'ahorro',    10);
