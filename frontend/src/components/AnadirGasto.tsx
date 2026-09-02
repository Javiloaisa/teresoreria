import { useEffect, useMemo, useRef, useState } from "react";

import { api, ErrorApi } from "../api";
import { clasificar, normalizar } from "../clasificar";
import { aNumero, hoyISO } from "../format";
import type { Categoria, Regla, Resumen } from "../types";
import { NOMBRE_CAT } from "../types";
import BotonesCategoria from "./BotonesCategoria";

/**
 * La pantalla que decide si la app se usa o se abandona: si apuntar un gasto
 * cuesta más de diez segundos, se deja de apuntar. De ahí que sea un solo
 * formulario sin pasos, con el importe enfocado al abrir y la fecha plegada.
 */
export default function AnadirGasto({
  reglas,
  conceptos,
  onGuardado,
  onReglaNueva,
}: {
  reglas: Regla[];
  conceptos: string[];
  onGuardado: (r: Resumen, concepto: string) => void;
  onReglaNueva: (r: Regla) => void;
}) {
  const [importe, setImporte] = useState("");
  const [concepto, setConcepto] = useState("");
  const [cat, setCat] = useState<Categoria | null>(null);
  const [elegidaAMano, setElegidaAMano] = useState(false);
  const [fecha, setFecha] = useState(hoyISO());
  const [verFecha, setVerFecha] = useState(false);
  const [aprender, setAprender] = useState(false);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const importeRef = useRef<HTMLInputElement>(null);
  useEffect(() => importeRef.current?.focus(), []);

  // La sugerencia se recalcula en el navegador con las reglas ya descargadas:
  // sin esperas ni peticiones mientras se escribe.
  const sugerida = useMemo(
    () => clasificar(concepto, reglas)?.cat ?? null,
    [concepto, reglas]
  );

  // Mientras no se toque un botón a mano, manda la sugerencia.
  useEffect(() => {
    if (!elegidaAMano) setCat(sugerida);
  }, [sugerida, elegidaAMano]);

  const patron = normalizar(concepto);
  const corrigeSugerencia = Boolean(sugerida && cat && cat !== sugerida);
  // Se ofrece aprender cuando hay algo que aprender: o se ha corregido la
  // sugerencia, o no había ninguna. Solo viene marcado en el primer caso,
  // porque una corrección es una señal clara; un concepto suelto ("Cena con
  // Marta") no merece una regla salvo que se pida.
  const puedeAprender = Boolean(cat && patron.length >= 3 && (corrigeSugerencia || !sugerida));

  useEffect(() => setAprender(corrigeSugerencia), [corrigeSugerencia]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    const n = aNumero(importe);
    if (n === null || n === 0) return setError("Pon un importe.");
    if (!concepto.trim()) return setError("Pon un concepto.");
    if (!cat) return setError("Elige un bote.");

    setOcupado(true);
    setError("");
    try {
      if (puedeAprender && aprender) {
        // Prioridad alta: lo que decide el usuario pesa más que las reglas
        // genéricas de arranque.
        onReglaNueva(await api.guardarRegla({ patron, cat, prioridad: 50 }));
      }
      const { resumen } = await api.crearGasto({
        concepto: concepto.trim(),
        importe: n,
        cat,
        fecha,
      });
      onGuardado(resumen, concepto.trim());
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No se ha podido guardar.");
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-4 p-4">
      <label className="block">
        <span className="text-xs text-stone-500">Importe</span>
        <div className="relative">
          <input
            ref={importeRef}
            inputMode="decimal"
            value={importe}
            onChange={(e) => setImporte(e.target.value)}
            placeholder="0,00"
            className="cifras w-full rounded-2xl border border-stone-200 bg-white py-5 pl-4 pr-12 text-4xl font-semibold outline-none focus:border-tinta"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-2xl text-stone-300">
            €
          </span>
        </div>
      </label>

      <label className="block">
        <span className="text-xs text-stone-500">Concepto</span>
        <input
          value={concepto}
          onChange={(e) => setConcepto(e.target.value)}
          list="conceptos-usados"
          autoComplete="off"
          placeholder="Mercadona, gasolina, cena…"
          className="w-full rounded-2xl border border-stone-200 bg-white px-4 py-3.5 outline-none focus:border-tinta"
        />
        <datalist id="conceptos-usados">
          {conceptos.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </label>

      <BotonesCategoria
        valor={cat}
        sugerida={sugerida}
        onCambiar={(c) => {
          setCat(c);
          setElegidaAMano(true);
        }}
      />

      {puedeAprender && (
        <label className="flex items-start gap-2 rounded-xl bg-white p-3 text-sm">
          <input
            type="checkbox"
            checked={aprender}
            onChange={(e) => setAprender(e.target.checked)}
            className="mt-0.5 h-4 w-4"
          />
          <span className="text-stone-600">
            A partir de ahora, «{patron}» va a{" "}
            <b className="text-stone-800">{cat && NOMBRE_CAT[cat]}</b>
          </span>
        </label>
      )}

      {/* La fecha está plegada: casi siempre es hoy, y desplegarla cuesta un
          toque solo cuando de verdad hace falta. */}
      {verFecha ? (
        <label className="block">
          <span className="text-xs text-stone-500">Fecha</span>
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="w-full rounded-xl border border-stone-200 bg-white px-4 py-2.5 outline-none focus:border-tinta"
          />
        </label>
      ) : (
        <button
          type="button"
          onClick={() => setVerFecha(true)}
          className="text-sm text-stone-400 underline underline-offset-2"
        >
          Hoy · cambiar fecha
        </button>
      )}

      {error && <p className="text-center text-sm text-rojo">{error}</p>}

      <button
        type="submit"
        disabled={ocupado}
        className="w-full rounded-2xl bg-tinta py-4 text-lg font-semibold text-crema disabled:opacity-40"
      >
        {ocupado ? "Guardando…" : "Guardar gasto"}
      </button>
    </form>
  );
}
