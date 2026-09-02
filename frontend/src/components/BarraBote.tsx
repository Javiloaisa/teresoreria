import { euros, eurosCortos } from "../format";
import type { Bote, Estado } from "../types";
import { NOMBRE_CAT } from "../types";

const RELLENO: Record<Estado, string> = {
  verde: "bg-verde",
  amarillo: "bg-ambar",
  rojo: "bg-rojo",
};

const TEXTO: Record<Estado, string> = {
  verde: "text-verde",
  amarillo: "text-ambar",
  rojo: "text-rojo",
};

const pct = (parte: number, total: number) =>
  total > 0 ? Math.min(100, Math.max(0, (parte / total) * 100)) : 0;

export default function BarraBote({ bote }: { bote: Bote }) {
  const { presupuesto, gastado, proyeccion, reservas, ritmo_diario, estado } = bote;
  const sinBase = presupuesto <= 0;

  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h3 className="font-semibold">{NOMBRE_CAT[bote.cat]}</h3>
        <span className="cifras text-sm text-stone-500">
          <span className={`font-semibold ${TEXTO[estado]}`}>{euros(gastado)}</span>
          {" / "}
          {eurosCortos(presupuesto)}
        </span>
      </div>

      <div className="relative mt-2 h-3 overflow-hidden rounded-full bg-stone-100">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ${RELLENO[estado]}`}
          style={{ width: `${pct(gastado, presupuesto)}%` }}
        />
        {/* La marca fina: dónde acabará el mes si se sigue a este ritmo. */}
        {!sinBase && proyeccion > gastado && (
          <div
            className="absolute inset-y-0 w-0.5 bg-stone-800/70"
            style={{ left: `calc(${pct(proyeccion, presupuesto)}% - 1px)` }}
            title={`Proyección a fin de mes: ${euros(proyeccion)}`}
          />
        )}
      </div>

      <p className="mt-2 text-xs text-stone-500">
        {sinBase ? (
          "Sin ingresos declarados este mes: declara uno en Ajustes."
        ) : (
          <>
            {reservas > 0 && <>Reserva {eurosCortos(reservas)} · </>}
            {ritmo_diario > 0 && <>{eurosCortos(ritmo_diario)}/día · </>}
            Proyección <span className={TEXTO[estado]}>{eurosCortos(proyeccion)}</span>
          </>
        )}
      </p>
    </div>
  );
}
