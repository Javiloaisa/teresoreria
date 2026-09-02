import { useCallback, useEffect, useState } from "react";

import { api, ErrorApi } from "../api";
import { euros, eurosCortos, fechaCorta, aNumero, hoyISO } from "../format";
import {
  activarAvisos,
  avisosActivados,
  desactivarAvisos,
  esIOS,
  estaInstalada,
  soportaPush,
} from "../push";
import type {
  Categoria,
  Config,
  Ingreso,
  Periodicidad,
  Recurrente,
  Regla,
  Resumen,
} from "../types";
import { CATEGORIAS, NOMBRE_CAT } from "../types";

const PERIODICIDADES: Periodicidad[] = [
  "mensual",
  "bimestral",
  "trimestral",
  "semestral",
  "anual",
];

const entrada =
  "w-full rounded-xl border border-stone-200 bg-white px-3 py-2.5 outline-none focus:border-tinta";

function Seccion({
  titulo,
  children,
  abierta = false,
}: {
  titulo: string;
  children: React.ReactNode;
  abierta?: boolean;
}) {
  const [ver, setVer] = useState(abierta);
  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-sm">
      <button
        onClick={() => setVer(!ver)}
        className="flex w-full items-center justify-between p-4 text-left font-semibold"
      >
        {titulo}
        <span className="text-stone-400">{ver ? "−" : "+"}</span>
      </button>
      {ver && <div className="space-y-3 border-t border-stone-100 p-4">{children}</div>}
    </section>
  );
}

export default function Ajustes({
  reglas,
  onResumen,
  onReglas,
  onSalir,
}: {
  reglas: Regla[];
  onResumen: (r: Resumen) => void;
  onReglas: (r: Regla[]) => void;
  onSalir: () => void;
}) {
  const [config, setConfig] = useState<Config | null>(null);
  const [ingresos, setIngresos] = useState<Ingreso[]>([]);
  const [recurrentes, setRecurrentes] = useState<Recurrente[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.config(), api.ingresos(), api.recurrentes()])
      .then(([c, i, r]) => {
        setConfig(c);
        setIngresos(i);
        setRecurrentes(r);
      })
      .catch(() => setError("No se han podido cargar los ajustes."));
  }, []);

  async function guardarConfig(cambios: Partial<Config>) {
    try {
      const r = await api.guardarConfig(cambios);
      setConfig(r.config);
      onResumen(r.resumen);
      setError("");
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No se ha podido guardar.");
    }
  }

  if (!config) {
    return <p className="p-8 text-center text-stone-400">{error || "Cargando…"}</p>;
  }

  return (
    <div className="space-y-3 p-3">
      {error && (
        <p className="rounded-xl bg-red-50 p-3 text-center text-sm text-rojo">{error}</p>
      )}

      <BaseYPorcentajes config={config} onGuardar={guardarConfig} />

      <Seccion titulo="Ingresos">
        <ListaIngresos
          ingresos={ingresos}
          setIngresos={setIngresos}
          onResumen={onResumen}
        />
      </Seccion>

      <Seccion titulo="Gastos recurrentes">
        <ListaRecurrentes
          recurrentes={recurrentes}
          setRecurrentes={setRecurrentes}
          onResumen={onResumen}
        />
      </Seccion>

      <Seccion titulo={`Reglas de clasificación (${reglas.length})`}>
        <ListaReglas reglas={reglas} onReglas={onReglas} />
      </Seccion>

      <Avisos config={config} onGuardar={guardarConfig} />

      <button
        onClick={async () => {
          await api.logout();
          onSalir();
        }}
        className="w-full rounded-2xl bg-white py-3 text-stone-500 shadow-sm"
      >
        Cerrar sesión
      </button>
    </div>
  );
}

// ── Base de cálculo y reparto ───────────────────────────────────────────────

function BaseYPorcentajes({
  config,
  onGuardar,
}: {
  config: Config;
  onGuardar: (c: Partial<Config>) => void;
}) {
  const [pcts, setPcts] = useState({
    pct_necesidades: config.pct_necesidades,
    pct_deseos: config.pct_deseos,
    pct_ahorro: config.pct_ahorro,
  });
  const suma = pcts.pct_necesidades + pcts.pct_deseos + pcts.pct_ahorro;

  return (
    <Seccion titulo="Base y reparto" abierta>
      <div className="flex gap-2">
        {(["real", "fijo"] as const).map((modo) => (
          <button
            key={modo}
            onClick={() => onGuardar({ base_mode: modo })}
            className={`flex-1 rounded-xl border py-2.5 text-sm ${
              config.base_mode === modo
                ? "border-tinta bg-tinta text-crema"
                : "border-stone-200 text-stone-600"
            }`}
          >
            {modo === "real" ? "Ingresos reales" : "Ingreso fijo"}
          </button>
        ))}
      </div>
      <p className="text-xs text-stone-500">
        {config.base_mode === "real"
          ? "Los botes se calculan sobre lo ingresado este mes. Hasta que registres algo se usa la media de los meses anteriores, marcada como estimada."
          : "Los botes se calculan siempre sobre el mismo ingreso base."}
      </p>

      {config.base_mode === "fijo" && (
        <label className="block">
          <span className="text-xs text-stone-500">Ingreso base mensual</span>
          <input
            inputMode="decimal"
            defaultValue={config.ingreso_base ?? ""}
            onBlur={(e) => {
              const n = aNumero(e.target.value);
              if (n !== null && n !== config.ingreso_base) onGuardar({ ingreso_base: n });
            }}
            className={`cifras ${entrada}`}
          />
        </label>
      )}

      <div className="grid grid-cols-3 gap-2">
        {CATEGORIAS.map((c, i) => {
          const clave = (["pct_necesidades", "pct_deseos", "pct_ahorro"] as const)[i];
          return (
            <label key={c} className="block">
              <span className="text-xs text-stone-500">{NOMBRE_CAT[c]}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={pcts[clave]}
                onChange={(e) =>
                  setPcts({ ...pcts, [clave]: Number(e.target.value) || 0 })
                }
                className={`cifras ${entrada}`}
              />
            </label>
          );
        })}
      </div>

      <div className="flex items-center justify-between">
        <span className={`text-sm ${suma === 100 ? "text-stone-400" : "text-rojo"}`}>
          Suman {suma} %
        </span>
        <button
          disabled={suma !== 100}
          onClick={() => onGuardar(pcts)}
          className="rounded-xl bg-tinta px-4 py-2 text-sm font-medium text-crema disabled:opacity-30"
        >
          Guardar reparto
        </button>
      </div>

      <label className="block">
        <span className="text-xs text-stone-500">
          Aviso en ámbar al llegar al {Math.round(config.umbral_amarillo * 100)} % del bote
        </span>
        <input
          type="range"
          min={50}
          max={100}
          step={5}
          defaultValue={Math.round(config.umbral_amarillo * 100)}
          onMouseUp={(e) =>
            onGuardar({ umbral_amarillo: Number((e.target as HTMLInputElement).value) / 100 })
          }
          onTouchEnd={(e) =>
            onGuardar({ umbral_amarillo: Number((e.target as HTMLInputElement).value) / 100 })
          }
          className="w-full"
        />
      </label>
    </Seccion>
  );
}

// ── Ingresos ────────────────────────────────────────────────────────────────

function ListaIngresos({
  ingresos,
  setIngresos,
  onResumen,
}: {
  ingresos: Ingreso[];
  setIngresos: (i: Ingreso[]) => void;
  onResumen: (r: Resumen) => void;
}) {
  const [concepto, setConcepto] = useState("");
  const [importe, setImporte] = useState("");

  async function anadir() {
    const n = aNumero(importe);
    if (n === null || !concepto.trim()) return;
    const r = await api.crearIngreso({
      concepto: concepto.trim(),
      importe: n,
      fecha: hoyISO(),
      tipo: "nomina",
    });
    setIngresos([r.ingreso, ...ingresos]);
    onResumen(r.resumen);
    setConcepto("");
    setImporte("");
  }

  return (
    <>
      <div className="flex gap-2">
        <input
          value={concepto}
          onChange={(e) => setConcepto(e.target.value)}
          placeholder="Nómina"
          className={entrada}
        />
        <input
          inputMode="decimal"
          value={importe}
          onChange={(e) => setImporte(e.target.value)}
          placeholder="0,00"
          className={`cifras w-28 ${entrada}`}
        />
        <button
          onClick={anadir}
          className="rounded-xl bg-tinta px-4 font-semibold text-crema"
        >
          +
        </button>
      </div>

      <ul className="divide-y divide-stone-100">
        {ingresos.map((i) => (
          <li key={i.id} className="flex items-center justify-between gap-2 py-2">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{i.concepto}</span>
              <span className="text-xs text-stone-400">{fechaCorta(i.fecha)}</span>
            </span>
            <span className="cifras text-sm font-medium">{euros(i.importe)}</span>
            <button
              onClick={async () => {
                const r = await api.borrarIngreso(i.id);
                setIngresos(ingresos.filter((x) => x.id !== i.id));
                onResumen(r.resumen);
              }}
              className="px-1 text-stone-300"
            >
              ×
            </button>
          </li>
        ))}
        {ingresos.length === 0 && (
          <li className="py-3 text-center text-sm text-stone-400">Sin ingresos aún.</li>
        )}
      </ul>
    </>
  );
}

// ── Recurrentes ─────────────────────────────────────────────────────────────

function ListaRecurrentes({
  recurrentes,
  setRecurrentes,
  onResumen,
}: {
  recurrentes: Recurrente[];
  setRecurrentes: (r: Recurrente[]) => void;
  onResumen: (r: Resumen) => void;
}) {
  const [nuevo, setNuevo] = useState({
    concepto: "",
    importe: "",
    periodicidad: "mensual" as Periodicidad,
    cat: "necesidad" as Categoria,
    mes_cargo: 1,
    dia_cargo: 1,
  });
  const [error, setError] = useState("");

  async function anadir() {
    const n = aNumero(nuevo.importe);
    if (n === null || !nuevo.concepto.trim()) return;
    try {
      const r = await api.crearRecurrente({
        concepto: nuevo.concepto.trim(),
        importe: n,
        periodicidad: nuevo.periodicidad,
        cat: nuevo.cat,
        mes_cargo: nuevo.periodicidad === "mensual" ? null : nuevo.mes_cargo,
        dia_cargo: nuevo.dia_cargo,
      });
      setRecurrentes([...recurrentes, r.recurrente]);
      onResumen(r.resumen);
      setNuevo({ ...nuevo, concepto: "", importe: "" });
      setError("");
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No se ha podido guardar.");
    }
  }

  return (
    <>
      <p className="text-xs text-stone-500">
        Un cargo de 480 € al año no se imputa entero al mes que llega: se reservan
        40 € cada mes y esa reserva descuenta del bote desde el día 1.
      </p>

      <ul className="divide-y divide-stone-100">
        {recurrentes.map((r) => (
          <li key={r.id} className="py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{r.concepto}</span>
                <span className="text-xs text-stone-400">
                  {euros(r.importe)} {r.periodicidad} · reserva{" "}
                  <b className="text-stone-600">{euros(r.reserva_mensual)}</b>/mes ·{" "}
                  {NOMBRE_CAT[r.cat]}
                </span>
              </span>
              <button
                onClick={async () => {
                  if (!confirm(`¿Borrar «${r.concepto}»?`)) return;
                  const resp = await api.borrarRecurrente(r.id);
                  setRecurrentes(recurrentes.filter((x) => x.id !== r.id));
                  onResumen(resp.resumen);
                }}
                className="px-1 text-stone-300"
              >
                ×
              </button>
            </div>

            {r.toca_cargar && !r.cargado_este_mes && (
              <button
                onClick={async () => {
                  const resp = await api.cargarRecurrente(r.id);
                  onResumen(resp.resumen);
                  setRecurrentes(
                    recurrentes.map((x) =>
                      x.id === r.id ? { ...x, cargado_este_mes: true } : x
                    )
                  );
                }}
                className="mt-1.5 w-full rounded-lg bg-stone-100 py-2 text-xs font-medium text-stone-700"
              >
                Registrar el cargo de este mes ({eurosCortos(r.importe)})
              </button>
            )}
            {r.cargado_este_mes && (
              <p className="mt-1 text-xs text-stone-400">Cargado este mes ✓</p>
            )}
          </li>
        ))}
        {recurrentes.length === 0 && (
          <li className="py-3 text-center text-sm text-stone-400">
            Sin recurrentes aún.
          </li>
        )}
      </ul>

      <div className="space-y-2 rounded-xl bg-stone-50 p-3">
        <div className="flex gap-2">
          <input
            value={nuevo.concepto}
            onChange={(e) => setNuevo({ ...nuevo, concepto: e.target.value })}
            placeholder="Seguro del coche"
            className={entrada}
          />
          <input
            inputMode="decimal"
            value={nuevo.importe}
            onChange={(e) => setNuevo({ ...nuevo, importe: e.target.value })}
            placeholder="0,00"
            className={`cifras w-24 ${entrada}`}
          />
        </div>
        <div className="flex gap-2">
          <select
            value={nuevo.periodicidad}
            onChange={(e) =>
              setNuevo({ ...nuevo, periodicidad: e.target.value as Periodicidad })
            }
            className={entrada}
          >
            {PERIODICIDADES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            value={nuevo.cat}
            onChange={(e) => setNuevo({ ...nuevo, cat: e.target.value as Categoria })}
            className={entrada}
          >
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>
                {NOMBRE_CAT[c]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-500">
          {nuevo.periodicidad !== "mensual" && (
            <label className="flex-1">
              Mes del cargo
              <input
                type="number"
                min={1}
                max={12}
                value={nuevo.mes_cargo}
                onChange={(e) => setNuevo({ ...nuevo, mes_cargo: Number(e.target.value) })}
                className={`cifras ${entrada}`}
              />
            </label>
          )}
          <label className="flex-1">
            Día del cargo (1-28)
            <input
              type="number"
              min={1}
              max={28}
              value={nuevo.dia_cargo}
              onChange={(e) => setNuevo({ ...nuevo, dia_cargo: Number(e.target.value) })}
              className={`cifras ${entrada}`}
            />
          </label>
        </div>
        {error && <p className="text-sm text-rojo">{error}</p>}
        <button
          onClick={anadir}
          className="w-full rounded-xl bg-tinta py-2.5 text-sm font-semibold text-crema"
        >
          Añadir recurrente
        </button>
      </div>
    </>
  );
}

// ── Reglas ──────────────────────────────────────────────────────────────────

function ListaReglas({
  reglas,
  onReglas,
}: {
  reglas: Regla[];
  onReglas: (r: Regla[]) => void;
}) {
  const [patron, setPatron] = useState("");
  const [cat, setCat] = useState<Categoria>("necesidad");

  return (
    <>
      <p className="text-xs text-stone-500">
        Al guardar un gasto se busca la primera regla cuyo texto aparezca en el
        concepto. La palabra tiene que acabar donde acaba la regla: «bar»
        reconoce «BAR MANOLO» pero no «Ferretería del barrio».
      </p>

      <div className="flex gap-2">
        <input
          value={patron}
          onChange={(e) => setPatron(e.target.value)}
          placeholder="mercadona"
          className={entrada}
        />
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value as Categoria)}
          className={entrada}
        >
          {CATEGORIAS.map((c) => (
            <option key={c} value={c}>
              {NOMBRE_CAT[c]}
            </option>
          ))}
        </select>
        <button
          onClick={async () => {
            if (patron.trim().length < 2) return;
            const nueva = await api.guardarRegla({ patron, cat, prioridad: 50 });
            onReglas([...reglas.filter((r) => r.id !== nueva.id), nueva]);
            setPatron("");
          }}
          className="rounded-xl bg-tinta px-4 font-semibold text-crema"
        >
          +
        </button>
      </div>

      <ul className="divide-y divide-stone-100">
        {[...reglas]
          .sort((a, b) => b.prioridad - a.prioridad || b.usos - a.usos)
          .map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 py-2">
              <span className="min-w-0 flex-1 truncate text-sm">{r.patron}</span>
              <span className="text-xs text-stone-400">
                {NOMBRE_CAT[r.cat]} · {r.usos} usos
              </span>
              <button
                onClick={async () => {
                  await api.borrarRegla(r.id);
                  onReglas(reglas.filter((x) => x.id !== r.id));
                }}
                className="px-1 text-stone-300"
              >
                ×
              </button>
            </li>
          ))}
      </ul>
    </>
  );
}

// ── Avisos ──────────────────────────────────────────────────────────────────

function Avisos({
  config,
  onGuardar,
}: {
  config: Config;
  onGuardar: (c: Partial<Config>) => void;
}) {
  const [activados, setActivados] = useState<boolean | null>(null);
  const [estado, setEstado] = useState<{
    configurado: boolean;
    dispositivos: number;
    proximo_repaso: string | null;
  } | null>(null);
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const enIOS = esIOS();
  const instalada = estaInstalada();
  // En iPhone, Safari ni siquiera ofrece push si la app no está en la pantalla
  // de inicio: sin este aviso, activar los avisos falla sin explicar por qué.
  const faltaInstalar = enIOS && !instalada;

  const refrescar = useCallback(async () => {
    setActivados(await avisosActivados().catch(() => false));
    setEstado(await api.estadoPush().catch(() => null));
  }, []);

  useEffect(() => {
    refrescar();
  }, [refrescar]);

  async function alternar() {
    setOcupado(true);
    setAviso("");
    try {
      if (activados) {
        await desactivarAvisos();
      } else {
        const r = await activarAvisos();
        if (r === "denegado")
          setAviso("Has bloqueado las notificaciones. Actívalas en los ajustes del navegador.");
        if (r === "no-soportado")
          setAviso("Este navegador no admite avisos, o faltan las claves en el servidor.");
      }
      await refrescar();
    } catch {
      setAviso("No se ha podido cambiar la suscripción.");
    } finally {
      setOcupado(false);
    }
  }

  async function probar() {
    setOcupado(true);
    setAviso("");
    try {
      await api.probarPush();
      setAviso("Enviado. Debería llegarte en un momento.");
    } catch (err) {
      setAviso(err instanceof ErrorApi ? err.message : "No se ha podido enviar.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Seccion titulo="Avisos en el móvil">
      <p className="text-xs text-stone-500">
        Un repaso al día a los tres botes. Si alguno va camino de pasarse, te
        llega un aviso. Uno por bote y mes: si se repitiera, dejarías de leerlo.
        Los primeros 5 días del mes no se avisa, porque con tan pocos datos la
        proyección es ruido.
      </p>

      {faltaInstalar ? (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <b>En iPhone hay que instalar la app antes.</b> Pulsa{" "}
          <b>Compartir</b> y luego <b>Añadir a pantalla de inicio</b>, ábrela
          desde ahí y vuelve a esta pantalla. Hace falta iOS 16.4 o superior.
        </p>
      ) : !soportaPush() ? (
        <p className="rounded-xl bg-stone-100 p-3 text-sm">
          Este navegador no admite notificaciones web.
        </p>
      ) : (
        <>
          <button
            onClick={alternar}
            disabled={ocupado || activados === null}
            className={`w-full rounded-xl py-3 font-semibold disabled:opacity-40 ${
              activados
                ? "border border-stone-200 bg-white text-stone-600"
                : "bg-tinta text-crema"
            }`}
          >
            {activados ? "Desactivar los avisos en este móvil" : "Activar los avisos"}
          </button>

          {activados && (
            <button
              onClick={probar}
              disabled={ocupado}
              className="w-full rounded-xl border border-stone-200 bg-white py-2.5 text-sm text-stone-600 disabled:opacity-40"
            >
              Enviarme un aviso de prueba
            </button>
          )}
        </>
      )}

      {aviso && <p className="text-sm text-stone-600">{aviso}</p>}

      <label className="block">
        <span className="text-xs text-stone-500">Hora del aviso diario</span>
        <input
          type="time"
          defaultValue={String(config.hora_aviso).slice(0, 5)}
          onBlur={(e) => {
            const v = e.target.value;
            if (v && v !== String(config.hora_aviso).slice(0, 5))
              onGuardar({ hora_aviso: v });
          }}
          className={`cifras ${entrada}`}
        />
      </label>

      {estado && (
        <p className="text-xs text-stone-400">
          {estado.configurado
            ? `${estado.dispositivos} ${
                estado.dispositivos === 1 ? "dispositivo suscrito" : "dispositivos suscritos"
              }`
            : "El servidor no tiene claves VAPID: los avisos están apagados."}
          {estado.proximo_repaso &&
            ` · próximo repaso ${new Date(estado.proximo_repaso).toLocaleString("es-ES", {
              weekday: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}`}
        </p>
      )}
    </Seccion>
  );
}
