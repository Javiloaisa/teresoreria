import type { Categoria } from "../types";
import { CATEGORIAS, NOMBRE_CAT } from "../types";

/** Los tres botes, siempre en el mismo orden y siempre a un dedo de distancia. */
export default function BotonesCategoria({
  valor,
  onCambiar,
  sugerida,
}: {
  valor: Categoria | null;
  onCambiar: (c: Categoria) => void;
  /** La que preseleccionaron las reglas, para poder marcarla como automática. */
  sugerida?: Categoria | null;
}) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {CATEGORIAS.map((c) => {
        const elegida = valor === c;
        return (
          <button
            key={c}
            type="button"
            onClick={() => onCambiar(c)}
            className={`rounded-xl border py-3 text-sm font-medium transition-colors ${
              elegida
                ? "border-tinta bg-tinta text-crema"
                : "border-stone-200 bg-white text-stone-600 active:bg-stone-50"
            }`}
          >
            {NOMBRE_CAT[c]}
            {sugerida === c && !elegida && (
              <span className="mt-0.5 block text-[10px] font-normal opacity-60">
                sugerida
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
