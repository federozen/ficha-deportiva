"""
⚽ Ficha Deportiva IA — Streamlit Community Cloud
"""

import streamlit as st
import anthropic
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import urllib.parse

# ── CONFIG ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚽ Ficha Deportiva IA",
    page_icon="⚽",
    layout="centered",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.main-header {
    background: linear-gradient(135deg, #00c853, #00897b);
    border-radius: 16px; padding: 20px 28px 16px; margin-bottom: 20px;
}
.main-header h1 {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 28px;
    color: #fff; margin: 0 0 4px 0; letter-spacing: -0.02em;
}
.main-header p { font-size: 13px; color: rgba(255,255,255,0.8); margin: 0; }
.result-box {
    background: #141414; border: 1px solid #1e1e1e; border-radius: 12px;
    padding: 18px 20px; color: #d0d0d0; font-size: 14px; line-height: 1.75;
    white-space: pre-wrap; word-break: break-word; margin-top: 12px;
}
.scrape-box {
    background: #0d1a0d; border: 1px solid #1a3a1a; border-radius: 10px;
    padding: 12px 16px; font-family: 'DM Mono', monospace; font-size: 11px;
    color: #4a8a4a; line-height: 1.6; margin-bottom: 10px;
}
.meta-info { font-family: 'DM Mono', monospace; font-size: 11px; color: #666; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>⚽ Ficha Deportiva IA</h1>
    <p>Contenido periodístico deportivo con IA · scraping gratuito en tiempo real</p>
</div>
""", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []

# ══════════════════════════════════════════════════════════════════════════════
# API KEY — lee desde st.secrets (deploy) o permite ingreso manual (local)
# ══════════════════════════════════════════════════════════════════════════════
def get_api_key(user_input: str) -> str:
    """Prioridad: secrets del deploy → input manual del usuario."""
    if st.secrets.get("ANTHROPIC_API_KEY"):
        return st.secrets["ANTHROPIC_API_KEY"]
    return user_input.strip()

# ══════════════════════════════════════════════════════════════════════════════
# SCRAPING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _get(url: str, timeout: int = 8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def ddg_snippets(query: str, max_results: int = 6) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    r = _get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for res in soup.select(".result")[:max_results]:
        title   = res.select_one(".result__title")
        snippet = res.select_one(".result__snippet")
        if snippet and len(snippet.get_text(strip=True)) > 30:
            results.append({
                "title":   title.get_text(strip=True) if title else "",
                "snippet": snippet.get_text(" ", strip=True),
            })
    return results


def wikipedia_summary(query: str, lang: str = "es") -> str:
    search_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={urllib.parse.quote_plus(query)}"
        f"&utf8=1&format=json&srlimit=1"
    )
    r = _get(search_url)
    if not r:
        return ""
    hits = r.json().get("query", {}).get("search", [])
    if not hits:
        return ""
    title = hits[0]["title"]
    extract_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&exintro=1&explaintext=1"
        f"&titles={urllib.parse.quote_plus(title)}&format=json"
    )
    r2 = _get(extract_url)
    if not r2:
        return ""
    pages = r2.json().get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "")
        paras = [p.strip() for p in extract.split("\n") if len(p.strip()) > 80]
        return " ".join(paras[:3])
    return ""


def sofascore_player(name: str) -> str:
    search = _get(
        f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page=0"
    )
    if not search:
        return ""
    players = search.json().get("players", [])
    if not players:
        return ""
    p   = players[0]["entity"]
    pid = p.get("id")
    lines = [f"Jugador: {p.get('name', name)}"]
    if p.get("position"):
        lines.append(f"Posición: {p['position']['name']}")
    if p.get("team"):
        lines.append(f"Club: {p['team']['name']}")
    if p.get("country"):
        lines.append(f"Nacionalidad: {p['country']['name']}")
    if p.get("dateOfBirthTimestamp"):
        dob = date.fromtimestamp(p["dateOfBirthTimestamp"])
        age = (date.today() - dob).days // 365
        lines.append(f"Edad: {age} años")
    stats_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/statistics/season")
    if stats_r:
        seasons = stats_r.json().get("seasons", [])
        if seasons:
            s     = seasons[0]
            stats = s.get("statistics", {})
            lines.append(f"\n— Estadísticas temporada {s.get('year', '')} —")
            for key, label in [
                ("goals", "Goles"), ("assists", "Asistencias"),
                ("appearances", "Partidos"), ("minutesPlayed", "Minutos"),
                ("rating", "Rating promedio"),
            ]:
                if key in stats:
                    lines.append(f"{label}: {stats[key]}")
    return "\n".join(lines)


def sofascore_team(name: str) -> str:
    search = _get(
        f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page=0"
    )
    if not search:
        return ""
    teams = search.json().get("teams", [])
    if not teams:
        return ""
    t   = teams[0]["entity"]
    tid = t.get("id")
    lines = [f"Equipo: {t.get('name', name)}"]
    if t.get("country"):
        lines.append(f"País: {t['country']['name']}")
    if t.get("tournament"):
        lines.append(f"Liga: {t['tournament']['name']}")
    matches_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/last/0")
    if matches_r:
        matches = matches_r.json().get("events", [])[:5]
        if matches:
            lines.append("\n— Últimos partidos —")
            for m in matches:
                hs  = m.get("homeScore", {}).get("current", "?")
                as_ = m.get("awayScore", {}).get("current", "?")
                lines.append(f"{m['homeTeam']['name']} {hs}-{as_} {m['awayTeam']['name']}")
    next_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/next/0")
    if next_r:
        upcoming = next_r.json().get("events", [])[:3]
        if upcoming:
            lines.append("\n— Próximos partidos —")
            for m in upcoming:
                ts    = m.get("startTimestamp")
                fecha = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else "?"
                lines.append(f"{fecha} — {m['homeTeam']['name']} vs {m['awayTeam']['name']}")
    return "\n".join(lines)


def sofascore_match(home: str, away: str) -> str:
    search = _get(
        f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(home + ' ' + away)}&page=0"
    )
    if not search:
        return ""
    events = search.json().get("events", [])
    if not events:
        return ""
    m   = events[0]["entity"]
    eid = m.get("id")
    hs  = m.get("homeScore", {}).get("current", "?")
    as_ = m.get("awayScore", {}).get("current", "?")
    status = m.get("status", {}).get("description", "")
    lines = [
        f"Partido: {m.get('homeTeam',{}).get('name',home)} {hs}-{as_} "
        f"{m.get('awayTeam',{}).get('name',away)} ({status})"
    ]
    if m.get("tournament"):
        lines.append(f"Competencia: {m['tournament']['name']}")
    stats_r = _get(f"https://api.sofascore.com/api/v1/event/{eid}/statistics")
    if stats_r:
        periods = stats_r.json().get("statistics", [])
        for period in periods[:1]:
            lines.append("\n— Estadísticas del partido —")
            for group in period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    lines.append(
                        f"{item.get('name','')}: {item.get('home','')} / {item.get('away','')}"
                    )
    return "\n".join(lines)


def scrape_context(params: dict) -> tuple[str, list[str]]:
    parts, sources = [], []
    tipo = params["type"]

    if tipo == "jugador":
        name = params["player"]
        sf = sofascore_player(name)
        if sf:
            parts.append(f"[SOFASCORE]\n{sf}"); sources.append("Sofascore")
        wiki = wikipedia_summary(f"{name} futbolista", "es") or wikipedia_summary(name, "es")
        if wiki:
            parts.append(f"[WIKIPEDIA]\n{wiki[:600]}"); sources.append("Wikipedia")
        snippets = ddg_snippets(f"{name} fútbol 2025 estadísticas noticias")
        if snippets:
            parts.append("[NOTICIAS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    elif tipo == "partido":
        home, away, comp = params["home"], params["away"], params.get("comp", "")
        sf = sofascore_match(home, away)
        if sf:
            parts.append(f"[SOFASCORE PARTIDO]\n{sf}"); sources.append("Sofascore")
        snippets = ddg_snippets(f"{home} vs {away} {comp} 2025 resultado")
        if snippets:
            parts.append("[NOTICIAS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    elif tipo == "equipo":
        name = params["team"]
        sf = sofascore_team(name)
        if sf:
            parts.append(f"[SOFASCORE]\n{sf}"); sources.append("Sofascore")
        wiki = wikipedia_summary(f"{name} club de fútbol", "es")
        if wiki:
            parts.append(f"[WIKIPEDIA]\n{wiki[:600]}"); sources.append("Wikipedia")
        snippets = ddg_snippets(f"{name} fútbol 2025 noticias")
        if snippets:
            parts.append("[NOTICIAS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    elif tipo == "libre":
        snippets = ddg_snippets(params.get("prompt", "") + " fútbol 2025")
        if snippets:
            parts.append("[BÚSQUEDA WEB]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    return "\n\n".join(parts), sources


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS & GENERACIÓN
# ══════════════════════════════════════════════════════════════════════════════

TONES = {
    "periodistico": "neutro, directo y profesional",
    "epico":        "épico, emotivo y cargado de dramatismo",
    "tecnico":      "técnico y analítico con vocabulario táctico específico",
    "critico":      "crítico y objetivo, señalando debilidades",
    "coloquial":    "coloquial con jerga del fútbol rioplatense",
}
FORMATS_PLAYER = {
    "ficha":   "una ficha periodística completa (posición, club, estilo de juego, fortalezas, debilidades, momento actual, estadísticas recientes, dato destacado)",
    "lead":    "un lead de apertura de nota (máximo 60 palabras, que enganche al lector desde la primera línea)",
    "perfil":  "un perfil biográfico (origen, carrera, hitos, personalidad, legado)",
    "cronica": "una crónica de rendimiento reciente (forma actual, últimas actuaciones, estadísticas, perspectivas)",
    "tweet":   "un hilo de Twitter/X de 6 tweets numerados con emojis, pensado para viralizar",
    "radio":   "un texto de 90 segundos de radio, con ritmo oral y sin tecnicismos visuales",
}
FORMATS_MATCH = {
    "cronica":    "una crónica completa del partido",
    "prepartido": "una previa del partido (contexto, claves tácticas, jugadores a seguir, pronóstico)",
    "flash":      "un flash de resultado en exactamente 80 palabras",
    "analisis":   "un análisis táctico (sistemas, presión, transiciones, puntos de quiebre)",
    "tweet":      "un hilo de Twitter/X de 5-7 tweets numerados con emojis",
}
FORMATS_TEAM = {
    "ficha":     "una ficha del equipo",
    "temporada": "un análisis de la temporada",
    "mercado":   "un resumen del mercado de pases",
    "once":      "un análisis del 11 titular",
    "proximo":   "una previa del próximo partido",
}


def build_prompt(p: dict, scraped_ctx: str) -> tuple[str, str]:
    sys_prompt = (
        "Sos un periodista deportivo argentino senior con 20 años de experiencia. "
        "Escribís para medios de primer nivel. Tu prosa es precisa, atractiva y refleja "
        "profundo conocimiento del deporte. Usás español rioplatense de forma natural. "
        "Cuando tenés datos reales los integrás de forma natural en el texto; cuando no "
        "los tenés, escribís con criterio periodístico sin inventar estadísticas específicas. "
        "El resultado siempre está listo para publicar, sin explicaciones ni meta-comentarios."
    )
    ctx_parts = []
    if scraped_ctx.strip():
        ctx_parts.append(
            f"DATOS REALES OBTENIDOS DE INTERNET (integrá los relevantes en el texto):\n{scraped_ctx}"
        )
    manual = p.get("context", "").strip()
    if manual:
        ctx_parts.append(f"DATOS ADICIONALES DEL PERIODISTA:\n{manual}")
    ctx_block = "\n\n".join(ctx_parts)

    tipo = p["type"]
    if tipo == "jugador":
        user = (
            f"Generá {FORMATS_PLAYER.get(p['format'], p['format'])} "
            f"sobre **{p['player']}**. Tono: {TONES.get(p['tone'], p['tone'])}."
        )
    elif tipo == "partido":
        score = f" (resultado: {p['score']})" if p.get("score") else ""
        user = (
            f"Generá {FORMATS_MATCH.get(p['format'], p['format'])} "
            f"del partido **{p['home']} vs {p['away']}**{score} · {p['comp']}."
        )
    elif tipo == "equipo":
        user = (
            f"Generá {FORMATS_TEAM.get(p['format'], p['format'])} "
            f"sobre **{p['team']}**."
        )
    else:
        user = p.get("prompt", "")

    if ctx_block:
        user += f"\n\n{ctx_block}"
    return sys_prompt, user


def get_label(p: dict) -> str:
    if p["type"] == "jugador": return f"{p['player']} · {p['format']}"
    if p["type"] == "partido": return f"{p['home']} vs {p['away']}"
    if p["type"] == "equipo":  return f"{p['team']} · {p['format']}"
    return (p.get("prompt") or "")[:45] + "…"


def generate(params: dict, api_key: str, do_scrape: bool):
    if not api_key:
        st.error("⚠️ Ingresá tu API key en la barra lateral.")
        return

    scraped_ctx, sources = "", []

    if do_scrape:
        with st.spinner("🌐 Scrapeando datos (Sofascore · Wikipedia · DuckDuckGo)…"):
            scraped_ctx, sources = scrape_context(params)
        if scraped_ctx:
            preview = scraped_ctx.replace("\n", "<br>")
            st.markdown(
                f'<div class="scrape-box"><strong>📡 Datos de: {", ".join(sources)}</strong>'
                f"<br><br>{preview}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("⚠️ No se encontraron datos online. Generando solo con IA…")

    sys_prompt, user_prompt = build_prompt(params, scraped_ctx)
    client = anthropic.Anthropic(api_key=api_key)

    with st.spinner("⚡ Generando contenido con IA…"):
        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1500,
                system=sys_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            st.error(f"❌ Error al llamar a la API: {e}")
            return

    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        st.error("La IA no devolvió texto. Intentá de nuevo.")
        return

    tokens      = getattr(response.usage, "output_tokens", "?")
    ts          = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    scrape_note = f" · 🌐 {', '.join(sources)}" if sources else " · sin scraping"
    st.markdown(
        f'<div class="meta-info">{tokens} tokens{scrape_note} · {ts}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="result-box">{text}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.download_button("📥 Descargar .txt", text,
                       file_name="ficha.txt", mime="text/plain")
    c2.download_button(
        "📥 Descargar .md",
        f"## {get_label(params)}\n\n{text}\n\n---\n*{ts}*",
        file_name="ficha.md", mime="text/markdown",
    )

    st.session_state.history.append({
        "ts": ts, "type": params["type"],
        "label": get_label(params), "result": text,
    })
    if len(st.session_state.history) > 25:
        st.session_state.history = st.session_state.history[-25:]


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🔑 API Key")

    # Si hay secret configurado en el deploy, no mostrar el input
    has_secret = bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
    if has_secret:
        st.success("✓ API key configurada en Secrets")
        api_key_input = ""
    else:
        api_key_input = st.text_input(
            "API Key de Anthropic", type="password", placeholder="sk-ant-api03-…",
            label_visibility="collapsed",
            help="Ingresá tu API key de Anthropic"
        )
        if api_key_input:
            if api_key_input.startswith("sk-ant-"):
                st.success("✓ Key lista")
            else:
                st.error("⚠ Debe empezar con sk-ant-")
        st.markdown("[↗ Obtener key gratis](https://console.anthropic.com/settings/keys)")

    api_key = get_api_key(api_key_input)

    st.divider()
    st.markdown("### 🌐 Datos en tiempo real")
    do_scrape = st.toggle(
        "Scraping gratuito", value=True,
        help="Busca datos reales gratis antes de generar. Sin costo extra.",
    )
    if do_scrape:
        st.caption("✅ Sofascore API\n✅ Wikipedia\n✅ DuckDuckGo")
    else:
        st.caption("Solo IA, sin datos externos")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_jugador, tab_partido, tab_equipo, tab_libre, tab_historial = st.tabs(
    ["🧑 Jugador", "🏟 Partido", "🛡 Equipo", "✍️ Libre", "📋 Historial"]
)

# ── JUGADOR ────────────────────────────────────────────────────────────────────
with tab_jugador:
    player = st.text_input("Nombre del jugador",
                           placeholder="Ej: Lionel Messi, Lautaro Martínez…")
    c1, c2 = st.columns(2)
    with c1:
        fmt_player = st.selectbox(
            "Formato", list(FORMATS_PLAYER.keys()),
            format_func=lambda k: {
                "ficha": "Ficha completa", "lead": "Lead de nota",
                "perfil": "Perfil biográfico", "cronica": "Crónica de rendimiento",
                "tweet": "Hilo Twitter/X", "radio": "Texto para radio",
            }[k], key="fmt_player",
        )
    with c2:
        tone = st.selectbox(
            "Tono", list(TONES.keys()),
            format_func=lambda k: {
                "periodistico": "Periodístico", "epico": "Épico",
                "tecnico": "Técnico", "critico": "Crítico",
                "coloquial": "Coloquial rioplatense",
            }[k], key="tone_player",
        )
    ctx_player = st.text_area(
        "Datos extra (opcional)",
        placeholder="Stats propias, notas, contexto de la nota…",
        height=80, key="ctx_player",
    )
    if st.button("⚡ Generar ficha del jugador", key="gen_jugador",
                 type="primary", use_container_width=True):
        if not player:
            st.warning("Ingresá el nombre del jugador.")
        else:
            generate(
                {"type": "jugador", "player": player, "format": fmt_player,
                 "tone": tone, "context": ctx_player},
                api_key, do_scrape,
            )

# ── PARTIDO ────────────────────────────────────────────────────────────────────
with tab_partido:
    c1, c2 = st.columns(2)
    with c1:
        home = st.text_input("Local", placeholder="Ej: River Plate", key="home")
    with c2:
        away = st.text_input("Visitante", placeholder="Ej: Boca Juniors", key="away")
    c3, c4 = st.columns(2)
    with c3:
        score = st.text_input("Resultado (si ya jugó)", placeholder="Ej: 2-1", key="score")
    with c4:
        comp = st.selectbox("Competencia", [
            "Champions League", "LaLiga", "Premier League", "Serie A",
            "Bundesliga", "Ligue 1", "Copa Libertadores", "Copa América",
            "Mundial", "Liga Profesional Argentina", "Eliminatorias", "Otra",
        ], key="comp")
    fmt_match = st.selectbox(
        "Formato", list(FORMATS_MATCH.keys()),
        format_func=lambda k: {
            "cronica": "Crónica completa", "prepartido": "Previa del partido",
            "flash": "Flash de resultado (80 palabras)",
            "analisis": "Análisis táctico", "tweet": "Hilo Twitter/X",
        }[k], key="fmt_match",
    )
    ctx_match = st.text_area(
        "Datos del partido (opcional)",
        placeholder="Goleadores, stats, incidencias…",
        height=80, key="ctx_match",
    )
    if st.button("⚡ Generar contenido del partido", key="gen_partido",
                 type="primary", use_container_width=True):
        if not home or not away:
            st.warning("Ingresá los dos equipos.")
        else:
            generate(
                {"type": "partido", "home": home, "away": away, "score": score,
                 "comp": comp, "format": fmt_match, "context": ctx_match},
                api_key, do_scrape,
            )

# ── EQUIPO ─────────────────────────────────────────────────────────────────────
with tab_equipo:
    team = st.text_input("Nombre del equipo",
                         placeholder="Ej: River Plate, Atlético de Madrid, PSG…",
                         key="team")
    fmt_team = st.selectbox(
        "Formato", list(FORMATS_TEAM.keys()),
        format_func=lambda k: {
            "ficha": "Ficha del equipo", "temporada": "Análisis de temporada",
            "mercado": "Resumen de mercado de pases",
            "once": "Análisis del 11 titular", "proximo": "Preview próximo partido",
        }[k], key="fmt_team",
    )
    ctx_team = st.text_area(
        "Datos extra (opcional)",
        placeholder="Posición en tabla, bajas, refuerzos…",
        height=80, key="ctx_team",
    )
    if st.button("⚡ Generar", key="gen_equipo", type="primary", use_container_width=True):
        if not team:
            st.warning("Ingresá el nombre del equipo.")
        else:
            generate(
                {"type": "equipo", "team": team, "format": fmt_team,
                 "context": ctx_team},
                api_key, do_scrape,
            )

# ── LIBRE ──────────────────────────────────────────────────────────────────────
with tab_libre:
    QUICK = [
        ("5 títulos",           "5 títulos periodísticos alternativos para una nota sobre: "),
        ("Traducir al inglés",  "Traducí al inglés deportivo periodístico: "),
        ("Resumir 60 palabras", "Resumí en exactamente 60 palabras: "),
        ("Datos curiosos",      "5 datos curiosos periodísticos sobre: "),
        ("Cierre épico",        "Escribí un párrafo de cierre épico para una nota sobre: "),
        ("Preguntas entrevista","10 preguntas para entrevistar a: "),
        ("Reescribir dinámico", "Reescribí este texto con más dinamismo y energía periodística: "),
    ]
    st.markdown("**Atajos rápidos**")
    cols = st.columns(4)
    for i, (label, prefix) in enumerate(QUICK):
        if cols[i % 4].button(label, key=f"quick_{i}", use_container_width=True):
            st.session_state["libre_text"] = prefix

    libre_text = st.text_area(
        "¿Qué necesitás?",
        value=st.session_state.get("libre_text", ""),
        placeholder=(
            "Ejemplos:\n"
            "• '5 títulos para una nota sobre el retiro de Riquelme'\n"
            "• '10 preguntas para entrevistar a Scaloni'\n"
            "• 'Resumí en 60 palabras: [texto largo]'"
        ),
        height=130, key="libre_textarea",
    )
    if st.button("⚡ Generar", key="gen_libre", type="primary", use_container_width=True):
        if not libre_text.strip():
            st.warning("Escribí tu consulta.")
        else:
            generate({"type": "libre", "prompt": libre_text.strip()}, api_key, do_scrape)

# ── HISTORIAL ──────────────────────────────────────────────────────────────────
with tab_historial:
    if not st.session_state.history:
        st.info("Todavía no generaste nada. Usá las otras pestañas.")
    else:
        if st.button("🗑 Borrar todo", type="secondary"):
            st.session_state.history = []
            st.rerun()
        for i, h in enumerate(reversed(st.session_state.history)):
            with st.expander(f"**{h['label']}** · {h['ts']}"):
                st.markdown(
                    f'<div class="result-box">{h["result"]}</div>',
                    unsafe_allow_html=True,
                )
                st.download_button(
                    "📥 Descargar", h["result"],
                    file_name=f"ficha_{h['label'][:30].replace(' ', '_')}.txt",
                    key=f"dl_hist_{i}",
                )
