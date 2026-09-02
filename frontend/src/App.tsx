import { useCallback, useEffect, useState } from "react";

import { api } from "./api";
import Ajustes from "./components/Ajustes";
import AnadirGasto from "./components/AnadirGasto";
import Login from "./components/Login";
import Nav, { type Pestana } from "./components/Nav";
import Resumen from "./components/Resumen";
import { nombreMes } from "./format";
import type { Regla, Resumen as TResumen } from "./types";

export default function App() {
  const [autenticado, setAutenticado] = useState<boolean | null>(null);
  const [configurado, setConfigurado] = useState(true);
  const [pestana, setPestana] = useState<Pestana>("resumen");

  // Estado compartido: el resumen es la fuente de verdad de la pantalla de
  // inicio, y casi todas las rutas que escriben lo devuelven ya recalculado,
  // así que basta con guardar lo que contestan.
  const [resumen, setResumen] = useState<TResumen | null>(null);
  const [reglas, setReglas] = useState<Regla[]>([]);
  const [conceptos, setConceptos] = useState<string[]>([]);

  useEffect(() => {
    api
      .me()
      .then((m) => {
        setAutenticado(m.autenticado);
        setConfigurado(m.configurado);
      })
      .catch(() => setAutenticado(false));
  }, []);

  const cargar = useCallback(async () => {
    const [r, rg, c] = await Promise.all([api.resumen(), api.reglas(), api.conceptos()]);
    setResumen(r);
    setReglas(rg);
    setConceptos(c);
  }, []);

  useEffect(() => {
    if (autenticado) cargar().catch(() => setAutenticado(false));
  }, [autenticado, cargar]);

  if (autenticado === null) {
    return <div className="p-8 text-center text-stone-400">Cargando…</div>;
  }

  if (!autenticado) {
    return (
      <Login configurado={configurado} onEntrar={() => setAutenticado(true)} />
    );
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col">
      <header className="sticky top-0 z-10 bg-tinta px-4 py-3 text-crema">
        <div className="flex items-baseline justify-between">
          <h1 className="text-lg font-semibold tracking-tight">Teresorería</h1>
          {resumen && (
            <span className="text-sm text-crema/70">{nombreMes(resumen.mes)}</span>
          )}
        </div>
      </header>

      <main className="flex-1 pb-24">
        {pestana === "resumen" && (
          <Resumen resumen={resumen} reglas={reglas} onResumen={setResumen} />
        )}
        {pestana === "anadir" && (
          <AnadirGasto
            reglas={reglas}
            conceptos={conceptos}
            onGuardado={(r, concepto) => {
              setResumen(r);
              // El concepto nuevo entra ya en el autocompletado, sin recargar.
              setConceptos((cs) => (cs.includes(concepto) ? cs : [concepto, ...cs]));
              setPestana("resumen");
            }}
            onReglaNueva={(regla) =>
              setReglas((rs) => [...rs.filter((r) => r.id !== regla.id), regla])
            }
          />
        )}
        {pestana === "ajustes" && (
          <Ajustes
            reglas={reglas}
            onResumen={setResumen}
            onReglas={setReglas}
            onSalir={() => setAutenticado(false)}
          />
        )}
      </main>

      <Nav actual={pestana} onCambiar={setPestana} />
    </div>
  );
}
