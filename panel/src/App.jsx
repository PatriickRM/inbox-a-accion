import { useCallback, useEffect, useMemo, useState } from "react";

const API = "/api"; // en desarrollo, Vite lo reenvia a FastAPI (ver vite.config.js)
const REFRESCO_MS = 15000;

const TIPOS = ["todos", "cotizacion", "soporte", "queja", "consulta", "spam"];
const NOMBRE_TIPO = {
  todos: "Todos",
  cotizacion: "Cotización",
  soporte: "Soporte",
  queja: "Queja",
  consulta: "Consulta",
  spam: "Spam",
};
const NOMBRE_URGENCIA = { alta: "Alta", media: "Media", baja: "Baja" };

// sessionStorage puede fallar (ventana privada, datos bloqueados): nunca debe romper la pagina.
// El token vive solo en esta pestana y se borra al cerrarla.
const leerToken = () => {
  try { return sessionStorage.getItem("api_token") || ""; } catch { return ""; }
};
const guardarToken = (t) => {
  try { t ? sessionStorage.setItem("api_token", t) : sessionStorage.removeItem("api_token"); } catch { /* sin almacenamiento */ }
};

async function llamar(ruta, token, opciones = {}) {
  let r;
  try {
    r = await fetch(`${API}${ruta}`, {
      ...opciones,
      headers: { "x-api-token": token, "Content-Type": "application/json", ...opciones.headers },
    });
  } catch {
    throw { tipo: "red", mensaje: "No se pudo conectar con la API. ¿Está corriendo uvicorn?" };
  }
  if (r.status === 401) throw { tipo: "token", mensaje: "Token incorrecto." };
  if (!r.ok) {
    let detalle = "";
    try { detalle = (await r.json()).detail; } catch { /* sin cuerpo */ }
    throw { tipo: "api", mensaje: `Error ${r.status}${detalle ? `: ${typeof detalle === "string" ? detalle : "datos no válidos"}` : ""}` };
  }
  return r.json();
}

function Acceso({ alIngresar, error }) {
  const [valor, setValor] = useState("");
  return (
    <main className="acceso">
      <h1>Inbox a Acción</h1>
      <p className="suave">Ingresa el token de tu API para ver los casos.</p>
      <form onSubmit={(e) => { e.preventDefault(); if (valor.trim()) alIngresar(valor.trim()); }}>
        <label htmlFor="token">Token de la API</label>
        <input id="token" type="password" autoComplete="off" value={valor}
               onChange={(e) => setValor(e.target.value)} />
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="primario">Entrar</button>
      </form>
      <p className="nota">El token queda solo en esta pestaña y se borra al cerrarla.</p>
    </main>
  );
}

function Resumen({ casos }) {
  const alta = casos.filter((c) => c.urgencia === "alta").length;
  const porTipo = (t) => casos.filter((c) => c.tipo === t).length;
  const datos = [
    ["Total", casos.length],
    ["Urgencia alta", alta],
    ["Cotizaciones", porTipo("cotizacion")],
    ["Soporte y quejas", porTipo("soporte") + porTipo("queja")],
  ];
  return (
    <section className="resumen" aria-label="Resumen">
      {datos.map(([etiqueta, n]) => (
        <div className="dato" key={etiqueta}>
          <span className="numero">{n}</span>
          <span className="suave">{etiqueta}</span>
        </div>
      ))}
    </section>
  );
}

function Acciones({ acciones }) {
  if (!acciones || acciones.length === 0) return <span className="suave">Sin acciones</span>;
  return (
    <ul className="acciones">
      {acciones.map((a, i) => (
        <li key={i} className={a.ok ? "ok" : "falla"} title={a.error || ""}>
          {a.ok ? "✓" : "✗"} {a.herramienta.replace(/_/g, " ")}
        </li>
      ))}
    </ul>
  );
}

function Tarjeta({ c }) {
  const fecha = new Date(c.fecha).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" });
  return (
    <article className={`caso u-${c.urgencia}`}>
      <header>
        <span className={`etiqueta t-${c.tipo}`}>{NOMBRE_TIPO[c.tipo] || c.tipo}</span>
        <span className={`urgencia u-${c.urgencia}`}>Urgencia {NOMBRE_URGENCIA[c.urgencia] || c.urgencia}</span>
        <time className="suave" dateTime={c.fecha}>{fecha}</time>
      </header>
      <h2>{c.cliente}</h2>
      <p>{c.resumen}</p>
      <p className="sugerida"><strong>Acción sugerida:</strong> {c.accion_sugerida}</p>
      <footer><Acciones acciones={c.acciones} /></footer>
    </article>
  );
}

function Probar({ token, alEnviar }) {
  const [texto, setTexto] = useState("");
  const [estado, setEstado] = useState({ enviando: false, error: "" });

  const enviar = async (e) => {
    e.preventDefault();
    if (!texto.trim()) return;
    setEstado({ enviando: true, error: "" });
    try {
      await llamar("/procesar", token, { method: "POST", body: JSON.stringify({ mensaje: texto.trim(), origen: "panel" }) });
      setTexto("");
      setEstado({ enviando: false, error: "" });
      alEnviar();
    } catch (err) {
      setEstado({ enviando: false, error: err.mensaje });
    }
  };

  return (
    <details className="probar">
      <summary>Probar con un mensaje</summary>
      <form onSubmit={enviar}>
        <label htmlFor="msg">Mensaje del cliente</label>
        <textarea id="msg" rows="3" maxLength="5000" value={texto} onChange={(e) => setTexto(e.target.value)}
                  placeholder="Ej: Necesito una cotización para automatizar mi facturación antes del viernes." />
        <p className="nota">Se procesa de verdad: usa Gemini y, si es urgente, te llega el aviso a Telegram.</p>
        {estado.error && <p className="error" role="alert">{estado.error}</p>}
        <button type="submit" className="primario" disabled={estado.enviando}>
          {estado.enviando ? "Procesando…" : "Procesar mensaje"}
        </button>
      </form>
    </details>
  );
}

export default function App() {
  const [token, setToken] = useState(leerToken);
  const [casos, setCasos] = useState([]);
  const [filtro, setFiltro] = useState("todos");
  const [estado, setEstado] = useState({ cargando: true, error: "", actualizado: null });
  const [errorAcceso, setErrorAcceso] = useState("");

  const cargar = useCallback(async () => {
    if (!token) return;
    try {
      const datos = await llamar("/casos?limite=200", token);
      setCasos(datos);
      setEstado({ cargando: false, error: "", actualizado: new Date() });
    } catch (err) {
      if (err.tipo === "token") {
        guardarToken("");
        setToken("");
        setErrorAcceso(err.mensaje);
        return;
      }
      setEstado((e) => ({ ...e, cargando: false, error: err.mensaje }));
    }
  }, [token]);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, REFRESCO_MS);
    return () => clearInterval(id);
  }, [cargar]);

  const visibles = useMemo(
    () => (filtro === "todos" ? casos : casos.filter((c) => c.tipo === filtro)),
    [casos, filtro]
  );

  if (!token) {
    return <Acceso error={errorAcceso} alIngresar={(t) => { guardarToken(t); setErrorAcceso(""); setToken(t); }} />;
  }

  return (
    <main className="panel">
      <div className="barra">
        <div>
          <h1>Inbox a Acción</h1>
          <p className="suave">
            {estado.actualizado
              ? `Actualizado ${estado.actualizado.toLocaleTimeString("es-PE", { timeStyle: "short" })} · se refresca solo`
              : "Cargando…"}
          </p>
        </div>
        <div className="botones">
          <button onClick={cargar}>Actualizar</button>
          <button onClick={() => { guardarToken(""); setToken(""); setCasos([]); }}>Salir</button>
        </div>
      </div>

      {estado.error && <p className="error" role="alert">{estado.error}</p>}

      <Resumen casos={casos} />
      <Probar token={token} alEnviar={cargar} />

      <div className="filtros" role="group" aria-label="Filtrar por tipo">
        {TIPOS.map((t) => (
          <button key={t} className={filtro === t ? "activo" : ""} aria-pressed={filtro === t} onClick={() => setFiltro(t)}>
            {NOMBRE_TIPO[t]}
          </button>
        ))}
      </div>

      <section className="lista" aria-label="Casos">
        {estado.cargando && <p className="suave">Cargando casos…</p>}
        {!estado.cargando && visibles.length === 0 && (
          <p className="vacio">
            {casos.length === 0
              ? "Aún no hay casos. Procesa un mensaje con el botón de arriba."
              : `No hay casos de tipo ${NOMBRE_TIPO[filtro].toLowerCase()}.`}
          </p>
        )}
        {visibles.map((c) => <Tarjeta key={c.id} c={c} />)}
      </section>
    </main>
  );
}
