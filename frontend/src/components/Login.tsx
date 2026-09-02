import { useState } from "react";

import { api, ErrorApi } from "../api";

export default function Login({
  configurado,
  onEntrar,
}: {
  configurado: boolean;
  onEntrar: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      await api.login(password);
      onEntrar();
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No se ha podido entrar.");
      setPassword("");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-tinta px-6 text-crema">
      <img src="/icon.svg" alt="" className="mb-6 h-20 w-20 rounded-2xl" />
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Teresorería</h1>
      <p className="mb-8 text-sm text-crema/60">Tus gastos, en tres botes.</p>

      {!configurado ? (
        <p className="max-w-xs rounded-xl bg-crema/10 p-4 text-center text-sm text-crema/80">
          Todavía no hay contraseña. Créala en el servidor con{" "}
          <code className="text-crema">docker compose exec api python manage.py set-password</code>.
        </p>
      ) : (
        <form onSubmit={entrar} className="w-full max-w-xs">
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Contraseña"
            className="w-full rounded-xl bg-crema/10 px-4 py-3 text-crema placeholder-crema/40 outline-none focus:bg-crema/15"
          />
          {error && <p className="mt-3 text-center text-sm text-red-300">{error}</p>}
          <button
            type="submit"
            disabled={enviando || !password}
            className="mt-4 w-full rounded-xl bg-crema py-3 font-semibold text-tinta disabled:opacity-40"
          >
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>
      )}
    </div>
  );
}
