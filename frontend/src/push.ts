// Suscripción a las notificaciones push desde el navegador.
import { api } from "./api";

export type ResultadoAlta = "ok" | "denegado" | "no-soportado";

export function soportaPush(): boolean {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** En iPhone, Safari solo ofrece push si la app está en la pantalla de inicio. */
export function esIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

export function estaInstalada(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // Safari en iOS no implementa display-mode y usa esto en su lugar.
    (navigator as { standalone?: boolean }).standalone === true
  );
}

/** La clave pública VAPID viaja en base64url y PushManager la quiere en bytes. */
function base64aBytes(base64: string): Uint8Array<ArrayBuffer> {
  const relleno = "=".repeat((4 - (base64.length % 4)) % 4);
  const normal = (base64 + relleno).replace(/-/g, "+").replace(/_/g, "/");
  const crudo = atob(normal);
  // Sobre un ArrayBuffer explícito: `new Uint8Array(n)` se tipa como
  // ArrayBufferLike y PushManager exige un ArrayBuffer de verdad.
  const bytes = new Uint8Array(new ArrayBuffer(crudo.length));
  for (let i = 0; i < crudo.length; i++) bytes[i] = crudo.charCodeAt(i);
  return bytes;
}

export async function avisosActivados(): Promise<boolean> {
  if (!soportaPush() || Notification.permission !== "granted") return false;
  const reg = await navigator.serviceWorker.ready;
  return Boolean(await reg.pushManager.getSubscription());
}

export async function activarAvisos(): Promise<ResultadoAlta> {
  if (!soportaPush()) return "no-soportado";

  const permiso = await Notification.requestPermission();
  if (permiso !== "granted") return "denegado";

  const { clave } = await api.clavePush();
  if (!clave) return "no-soportado";

  const reg = await navigator.serviceWorker.ready;
  let suscripcion = await reg.pushManager.getSubscription();
  if (!suscripcion) {
    suscripcion = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: base64aBytes(clave),
    });
  }
  await api.suscribirPush(suscripcion.toJSON());
  return "ok";
}

export async function desactivarAvisos(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const suscripcion = await reg.pushManager.getSubscription();
  if (!suscripcion) return;

  // Primero se borra en el servidor: si solo se cancelara en el navegador, el
  // endpoint muerto se quedaría en la tabla dando errores en cada aviso.
  await api.bajaPush(suscripcion.endpoint).catch(() => {});
  await suscripcion.unsubscribe().catch(() => {});
}
