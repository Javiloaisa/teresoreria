import type {
  Config,
  Gasto,
  Ingreso,
  Recurrente,
  Regla,
  Resumen,
} from "./types";

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje);
  }
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const r = await fetch(`/api${ruta}`, {
    ...opciones,
    headers: { "Content-Type": "application/json", ...opciones.headers },
    credentials: "same-origin",
  });

  if (!r.ok) {
    let detalle = `Error ${r.status}`;
    try {
      const cuerpo = await r.json();
      // FastAPI manda el motivo en `detail`; si es un fallo de validación viene
      // como lista de campos y ahí no hay nada legible que enseñar.
      if (typeof cuerpo.detail === "string") detalle = cuerpo.detail;
    } catch {
      /* respuesta sin JSON: nos quedamos con el código */
    }
    throw new ErrorApi(r.status, detalle);
  }
  return r.json();
}

const enviar = <T,>(ruta: string, metodo: string, cuerpo?: unknown) =>
  pedir<T>(ruta, { method: metodo, body: cuerpo ? JSON.stringify(cuerpo) : undefined });

// Muchas rutas devuelven el resumen ya recalculado junto al objeto que tocaron:
// así la barra del resumen se actualiza sin una segunda llamada.
type ConResumen<K extends string, T> = { [P in K]: T } & { resumen: Resumen };

export const api = {
  // Sesión
  me: () => pedir<{ autenticado: boolean; configurado: boolean }>("/me"),
  login: (password: string) => enviar<{ ok: true }>("/login", "POST", { password }),
  logout: () => enviar<{ ok: true }>("/logout", "POST"),

  // Resumen
  resumen: () => pedir<Resumen>("/resumen"),

  // Gastos
  gastos: (mes?: string) => pedir<Gasto[]>(`/gastos${mes ? `?mes=${mes}` : ""}`),
  conceptos: () => pedir<string[]>("/conceptos"),
  crearGasto: (datos: Partial<Gasto>) =>
    enviar<ConResumen<"gasto", Gasto>>("/gastos", "POST", datos),
  editarGasto: (id: number, datos: Partial<Gasto>) =>
    enviar<ConResumen<"gasto", Gasto>>(`/gastos/${id}`, "PATCH", datos),
  borrarGasto: (id: number) =>
    enviar<{ ok: true; resumen: Resumen }>(`/gastos/${id}`, "DELETE"),

  // Ingresos
  ingresos: () => pedir<Ingreso[]>("/ingresos"),
  crearIngreso: (datos: Partial<Ingreso>) =>
    enviar<ConResumen<"ingreso", Ingreso>>("/ingresos", "POST", datos),
  borrarIngreso: (id: number) =>
    enviar<{ ok: true; resumen: Resumen }>(`/ingresos/${id}`, "DELETE"),

  // Recurrentes
  recurrentes: () => pedir<Recurrente[]>("/recurrentes"),
  crearRecurrente: (datos: Partial<Recurrente>) =>
    enviar<ConResumen<"recurrente", Recurrente>>("/recurrentes", "POST", datos),
  editarRecurrente: (id: number, datos: Partial<Recurrente>) =>
    enviar<ConResumen<"recurrente", Recurrente>>(`/recurrentes/${id}`, "PATCH", datos),
  borrarRecurrente: (id: number) =>
    enviar<{ ok: true; resumen: Resumen }>(`/recurrentes/${id}`, "DELETE"),
  cargarRecurrente: (id: number) =>
    enviar<ConResumen<"gasto", Gasto>>(`/recurrentes/${id}/cargar`, "POST"),

  // Reglas
  reglas: () => pedir<Regla[]>("/reglas"),
  guardarRegla: (datos: { patron: string; cat: string; prioridad?: number }) =>
    enviar<Regla>("/reglas", "POST", datos),
  borrarRegla: (id: number) => enviar<{ ok: true }>(`/reglas/${id}`, "DELETE"),

  // Notificaciones push
  clavePush: () => pedir<{ clave: string; configurado: boolean }>("/push/clave"),
  estadoPush: () =>
    pedir<{ configurado: boolean; dispositivos: number; proximo_repaso: string | null }>(
      "/push/estado"
    ),
  suscribirPush: (suscripcion: unknown) =>
    enviar<{ ok: true }>("/push/suscribir", "POST", suscripcion),
  bajaPush: (endpoint: string) => enviar<{ ok: true }>("/push/baja", "POST", { endpoint }),
  probarPush: () => enviar<{ entregados: number }>("/push/prueba", "POST"),

  // Configuración
  config: () => pedir<Config>("/config"),
  guardarConfig: (datos: Partial<Config>) =>
    enviar<ConResumen<"config", Config>>("/config", "PATCH", datos),
};
