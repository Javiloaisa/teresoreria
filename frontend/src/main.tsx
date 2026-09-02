import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);

// El service worker es lo que hace la app instalable en el móvil (y, en F3,
// lo que recibirá los avisos). Si el navegador no lo soporta, da igual: la app
// funciona lo mismo, solo que sin instalar.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* sin service worker se sigue usando la app con normalidad */
    });
  });
}
