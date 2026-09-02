// Service worker de Teresorería.
//
// Hace dos cosas hoy: existir (sin él la app no es instalable en el móvil) y
// cachear el armazón para que abra al instante. El manejador de `push` llega
// en F3; el hueco está preparado abajo.

const CACHE = "teresoreria-v1";
const ARMAZON = ["/", "/index.html", "/manifest.webmanifest", "/icon-192.png"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ARMAZON)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  // Fuera las versiones viejas del caché, o una actualización no llegaría nunca.
  evento.waitUntil(
    caches
      .keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const url = new URL(evento.request.url);

  // La API nunca se cachea: son números y tienen que ser los de ahora mismo.
  if (url.pathname.startsWith("/api/") || evento.request.method !== "GET") return;

  // Red primero y caché como red de seguridad: así una versión nueva se ve en
  // cuanto hay cobertura, pero la app abre igual en el metro.
  evento.respondWith(
    fetch(evento.request)
      .then((respuesta) => {
        const copia = respuesta.clone();
        caches.open(CACHE).then((c) => c.put(evento.request, copia));
        return respuesta;
      })
      .catch(() => caches.match(evento.request).then((r) => r || caches.match("/index.html")))
  );
});

// ── F3: notificaciones push ─────────────────────────────────────────────────
// Cuando llegue la fase 3, esto se rellena con el aviso y su clic:
//
// self.addEventListener("push", (evento) => {
//   const datos = evento.data.json();
//   evento.waitUntil(self.registration.showNotification(datos.titulo, {
//     body: datos.cuerpo, icon: "/icon-192.png", badge: "/icon-192.png",
//   }));
// });
//
// self.addEventListener("notificationclick", (evento) => {
//   evento.notification.close();
//   evento.waitUntil(self.clients.openWindow("/"));
// });
