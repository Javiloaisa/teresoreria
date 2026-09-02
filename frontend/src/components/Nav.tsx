export type Pestana = "resumen" | "anadir" | "ajustes";

const PESTANAS: { id: Pestana; texto: string; icono: string }[] = [
  { id: "resumen", texto: "Resumen", icono: "▤" },
  { id: "anadir", texto: "Añadir", icono: "+" },
  { id: "ajustes", texto: "Ajustes", icono: "⚙" },
];

export default function Nav({
  actual,
  onCambiar,
}: {
  actual: Pestana;
  onCambiar: (p: Pestana) => void;
}) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-10 mx-auto flex max-w-lg border-t border-stone-200 bg-white"
      // Deja sitio a la barra de gestos del iPhone con la app instalada.
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      {PESTANAS.map((p) => {
        const activa = p.id === actual;
        const destacada = p.id === "anadir";
        return (
          <button
            key={p.id}
            onClick={() => onCambiar(p.id)}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-xs transition-colors ${
              activa ? "text-tinta" : "text-stone-400"
            }`}
          >
            <span
              className={
                destacada
                  ? `flex h-8 w-8 items-center justify-center rounded-full text-xl leading-none ${
                      activa ? "bg-tinta text-crema" : "bg-stone-200 text-stone-500"
                    }`
                  : "text-lg leading-none"
              }
            >
              {p.icono}
            </span>
            <span className={activa ? "font-medium" : ""}>{p.texto}</span>
          </button>
        );
      })}
    </nav>
  );
}
