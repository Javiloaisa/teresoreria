import { useState } from "react";

import { euros, eurosCortos, fechaCorta } from "../format";
import type { Gasto, Regla, Resumen as TResumen } from "../types";
import BarraBote from "./BarraBote";
import EditarGasto from "./EditarGasto";

export default function Resumen({
  resumen,
  reglas,
  onResumen,
}: {
  resumen: TResumen | null;
  reglas: Regla[];
  onResumen: (r: TResumen) => void;
}) {
  const [editando, setEditando] = useState<Gasto | null>(null);

  if (!resumen) {
    return <p className="p-8 text-center text-stone-400">Cargando…</p>;
  }

  return (
    <div className="space-y-3 p-3">
      <div className="flex items-baseline justify-between px-1 text-sm text-stone-500">
        <span>
          Base{" "}
          <span className="cifras font-medium text-stone-700">
            {eurosCortos(resumen.base)}
          </span>
          {resumen.base_estimada && (
            // Importa decirlo: mientras no haya ingresos del mes, los botes se
            // calculan sobre una media, no sobre dinero real.
            <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
              estimada
            </span>
          )}
        </span>
        <span>
          {resumen.dias_restantes === 0
            ? "último día"
            : `quedan ${resumen.dias_restantes} días`}
        </span>
      </div>

      {resumen.botes.map((b) => (
        <BarraBote key={b.cat} bote={b} />
      ))}

      <section className="rounded-2xl bg-white p-4 shadow-sm">
        <h3 className="mb-2 font-semibold">Últimos gastos</h3>
        {resumen.ultimos_gastos.length === 0 ? (
          <p className="py-4 text-center text-sm text-stone-400">
            Todavía no hay gastos este mes.
          </p>
        ) : (
          <ul className="divide-y divide-stone-100">
            {resumen.ultimos_gastos.map((g) => (
              <li key={g.id}>
                <button
                  onClick={() => setEditando(g)}
                  className="flex w-full items-center justify-between gap-3 py-2.5 text-left active:bg-stone-50"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{g.concepto}</span>
                    <span className="text-xs text-stone-400">
                      {fechaCorta(g.fecha)}
                      {g.recurrente_id && " · recurrente"}
                    </span>
                  </span>
                  <span className="cifras shrink-0 font-medium">{euros(g.importe)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {editando && (
        <EditarGasto
          gasto={editando}
          reglas={reglas}
          onCerrar={() => setEditando(null)}
          onGuardado={(r) => {
            onResumen(r);
            setEditando(null);
          }}
        />
      )}
    </div>
  );
}
