const EUROS = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
});

const EUROS_REDONDOS = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

export const euros = (n: number) => EUROS.format(n ?? 0);

/** Para titulares y avisos, donde los céntimos solo estorban. */
export const eurosCortos = (n: number) => EUROS_REDONDOS.format(n ?? 0);

const DIA_MES = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short" });

export function fechaCorta(iso: string): string {
  return DIA_MES.format(new Date(`${iso}T00:00:00`));
}

export function nombreMes(mes: string): string {
  const [anio, m] = mes.split("-");
  const nombre = new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" })
    .format(new Date(Number(anio), Number(m) - 1, 1));
  return nombre.charAt(0).toUpperCase() + nombre.slice(1);
}

/** Acepta la coma decimal española además del punto. */
export function aNumero(texto: string): number | null {
  const limpio = texto.replace(/\s/g, "").replace(",", ".");
  if (!limpio) return null;
  const n = Number(limpio);
  return Number.isFinite(n) ? n : null;
}

export const hoyISO = () => {
  const d = new Date();
  const dos = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
};
