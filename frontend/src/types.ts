export type Categoria = "necesidad" | "deseo" | "ahorro";
export type Estado = "verde" | "amarillo" | "rojo";
export type Periodicidad =
  | "mensual"
  | "bimestral"
  | "trimestral"
  | "semestral"
  | "anual";

export const CATEGORIAS: Categoria[] = ["necesidad", "deseo", "ahorro"];

export const NOMBRE_CAT: Record<Categoria, string> = {
  necesidad: "Necesidades",
  deseo: "Deseos",
  ahorro: "Ahorro",
};

// Los importes llegan como número: la API los serializa desde Decimal con dos
// decimales, y en estas magnitudes no hay pérdida que preocupe.
export interface Bote {
  cat: Categoria;
  pct: number;
  presupuesto: number;
  reservas: number;
  variable: number;
  gastado: number;
  restante: number;
  ritmo_diario: number;
  proyeccion: number;
  estado: Estado;
  avisable: boolean;
}

export interface Gasto {
  id: number;
  fecha: string;
  concepto: string;
  importe: number;
  cat: Categoria;
  recurrente_id: number | null;
  regla_id: number | null;
  nota: string | null;
}

export interface Resumen {
  mes: string;
  dia: number;
  dias_mes: number;
  dias_restantes: number;
  base: number;
  base_estimada: boolean;
  base_mode: "fijo" | "real";
  ingresos_mes: number;
  botes: Bote[];
  ultimos_gastos: Gasto[];
}

export interface Ingreso {
  id: number;
  fecha: string;
  concepto: string;
  importe: number;
  tipo: "nomina" | "factura" | "otro";
}

export interface Recurrente {
  id: number;
  concepto: string;
  importe: number;
  periodicidad: Periodicidad;
  mes_cargo: number | null;
  dia_cargo: number | null;
  cat: Categoria;
  activo: boolean;
  reserva_mensual: number;
  toca_cargar: boolean;
  cargado_este_mes: boolean;
}

export interface Regla {
  id: number;
  patron: string;
  cat: Categoria;
  prioridad: number;
  usos: number;
}

export interface Config {
  base_mode: "fijo" | "real";
  ingreso_base: number | null;
  pct_necesidades: number;
  pct_deseos: number;
  pct_ahorro: number;
  umbral_amarillo: number;
  hora_aviso: string;
}
