import type { Categoria, Regla } from "./types";

/**
 * Copia en TypeScript de `api/clasificar.py`.
 *
 * Está duplicado a propósito: preseleccionar la categoría mientras se escribe
 * el concepto tiene que ser instantáneo, y una ida y vuelta al servidor por
 * cada tecla no lo es. Las reglas se descargan una vez al abrir la app.
 *
 * Si se cambia la forma de casar, hay que cambiarla en los dos sitios. La
 * versión de Python es la de referencia y la que tiene los tests.
 */

export function normalizar(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "") // los acentos que separa NFKD
    .replace(/\s+/g, " ");
}

const PLURALES = ["", "s", "es"];

/** El patrón casa si la palabra acaba donde acaba él (o sigue con el plural). */
export function casa(patron: string, texto: string): boolean {
  let desde = texto.indexOf(patron);
  while (desde !== -1) {
    const resto = texto.slice(desde + patron.length);
    for (const sufijo of PLURALES) {
      if (resto.startsWith(sufijo)) {
        const cola = resto.slice(sufijo.length);
        if (!cola || !/\p{L}/u.test(cola[0])) return true;
      }
    }
    desde = texto.indexOf(patron, desde + 1);
  }
  return false;
}

export function clasificar(
  concepto: string,
  reglas: Regla[]
): { cat: Categoria; reglaId: number } | null {
  const texto = normalizar(concepto);
  if (!texto) return null;

  const ordenadas = [...reglas].sort(
    (a, b) => b.prioridad - a.prioridad || b.usos - a.usos || a.id - b.id
  );

  for (const regla of ordenadas) {
    const patron = normalizar(regla.patron);
    if (patron && casa(patron, texto)) return { cat: regla.cat, reglaId: regla.id };
  }
  return null;
}
