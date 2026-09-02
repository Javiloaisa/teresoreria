import { useState } from "react";

import { api, ErrorApi } from "../api";
import { normalizar } from "../clasificar";
import { aNumero, euros } from "../format";
import type { Categoria, Gasto, Regla, Resumen } from "../types";
import { NOMBRE_CAT } from "../types";
import BotonesCategoria from "./BotonesCategoria";

export default function EditarGasto({
  gasto,
  reglas,
  onCerrar,
  onGuardado,
}: {
  gasto: Gasto;
  reglas: Regla[];
  onCerrar: () => void;
  onGuardado: (r: Resumen) => void;
}) {
  const [concepto, setConcepto] = useState(gasto.concepto);
  const [importe, setImporte] = useState(String(gasto.importe).replace(".", ","));
  const [cat, setCat] = useState<Categoria>(gasto.cat);
  const [fecha, setFecha] = useState(gasto.fecha);
  const [aprender, setAprender] = useState(true);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cambioDeCategoria = cat !== gasto.cat;
  const patron = normalizar(concepto);
  const yaHayRegla = reglas.some((r) => normalizar(r.patron) === patron && r.cat === cat);

  async function guardar() {
    const n = aNumero(importe);
    if (n === null) return setError("Ese importe no se entiende.");

    setOcupado(true);
    setError("");
    try {
      // Si se ha corregido la categoría, se le enseña a la app antes de
      // guardar: la próxima vez ese concepto irá solo al bote correcto.
      if (cambioDeCategoria && aprender && !yaHayRegla) {
        // Prioridad alta: lo que dice el usuario manda sobre las reglas de
        // arranque, que son genéricas.
        await api.guardarRegla({ patron, cat, prioridad: 50 });
      }
      const { resumen } = await api.editarGasto(gasto.id, {
        concepto,
        importe: n,
        cat,
        fecha,
      });
      onGuardado(resumen);
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No se ha podido guardar.");
      setOcupado(false);
    }
  }

  async function borrar() {
    if (!confirm(`¿Borrar «${gasto.concepto}» de ${euros(gasto.importe)}?`)) return;
    setOcupado(true);
    try {
      const { resumen } = await api.borrarGasto(gasto.id);
      onGuardado(resumen);
    } catch {
      setError("No se ha podido borrar.");
      setOcupado(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-20 flex items-end bg-black/40"
      onClick={onCerrar}
    >
      <div
        className="mx-auto w-full max-w-lg space-y-3 rounded-t-3xl bg-crema p-4 pb-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-1 h-1 w-10 rounded-full bg-stone-300" />

        {gasto.recurrente_id && (
          <p className="rounded-xl bg-stone-100 p-3 text-xs text-stone-600">
            Es el cargo de un gasto recurrente: ya estaba reservado desde el día 1,
            así que no cuenta para el ritmo ni mueve la barra.
          </p>
        )}

        <label className="block">
          <span className="text-xs text-stone-500">Importe</span>
          <input
            inputMode="decimal"
            value={importe}
            onChange={(e) => setImporte(e.target.value)}
            className="cifras w-full rounded-xl border border-stone-200 bg-white px-4 py-3 text-2xl font-semibold outline-none focus:border-tinta"
          />
        </label>

        <label className="block">
          <span className="text-xs text-stone-500">Concepto</span>
          <input
            value={concepto}
            onChange={(e) => setConcepto(e.target.value)}
            className="w-full rounded-xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-tinta"
          />
        </label>

        <BotonesCategoria valor={cat} onCambiar={setCat} />

        {cambioDeCategoria && !yaHayRegla && (
          <label className="flex items-start gap-2 rounded-xl bg-white p-3 text-sm">
            <input
              type="checkbox"
              checked={aprender}
              onChange={(e) => setAprender(e.target.checked)}
              className="mt-0.5 h-4 w-4"
            />
            <span className="text-stone-600">
              A partir de ahora, «{patron}» va a{" "}
              <b className="text-stone-800">{NOMBRE_CAT[cat]}</b>
            </span>
          </label>
        )}

        <label className="block">
          <span className="text-xs text-stone-500">Fecha</span>
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="w-full rounded-xl border border-stone-200 bg-white px-4 py-2.5 outline-none focus:border-tinta"
          />
        </label>

        {error && <p className="text-center text-sm text-rojo">{error}</p>}

        <div className="flex gap-2 pt-1">
          <button
            onClick={borrar}
            disabled={ocupado}
            className="rounded-xl border border-stone-200 bg-white px-4 py-3 text-rojo disabled:opacity-40"
          >
            Borrar
          </button>
          <button
            onClick={guardar}
            disabled={ocupado}
            className="flex-1 rounded-xl bg-tinta py-3 font-semibold text-crema disabled:opacity-40"
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
