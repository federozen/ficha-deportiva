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

# ── FECHA Y TEMPORADA VIGENTE ──────────────────────────────────────────────────
def hoy() -> str:
    return datetime.now().strftime("%d/%m/%Y")

def año_actual() -> int:
    return datetime.now().year

def temporada_vigente() -> str:
    """
    Devuelve la temporada en curso según el mes del año.
    - Ago–mayo: temporada europea en curso, ej. 2024/2025
    - Jun–jul:  receso europeo; ligas sudamericanas activas
    """
    now   = datetime.now()
    year  = now.year
    month = now.month
    if month >= 8:
        return f"{year}/{year+1} (Europa) · {year} (Sudamérica)"
    elif month <= 5:
        return f"{year-1}/{year} (Europa) · {year} (Sudamérica)"
    else:
        return f"{year} (receso europeo · temporada sudamericana en curso)"

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


def _sofascore_player_id(name: str) -> tuple[int | None, dict]:
    """Busca el jugador en Sofascore y devuelve (id, entity_dict)."""
    search = _get(
        f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page=0"
    )
    if not search:
        return None, {}
    players = search.json().get("players", [])
    if not players:
        return None, {}
    entity = players[0]["entity"]
    return entity.get("id"), entity


def sofascore_player_temporada(name: str) -> str:
    """Stats detalladas de la temporada en curso."""
    pid, p = _sofascore_player_id(name)
    if not pid:
        return ""

    lines = [f"JUGADOR: {p.get('name', name)}"]
    if p.get("position"):
        lines.append(f"Posición: {p['position']['name']}")
    if p.get("team"):
        lines.append(f"Club actual: {p['team']['name']}")
    if p.get("country"):
        lines.append(f"Nacionalidad: {p['country']['name']}")
    if p.get("dateOfBirthTimestamp"):
        dob = date.fromtimestamp(p["dateOfBirthTimestamp"])
        age = (date.today() - dob).days // 365
        lines.append(f"Edad: {age} años ({dob})")

    # Stats de TODAS las temporadas disponibles (priorizamos la más reciente)
    stats_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/statistics/season")
    if stats_r:
        seasons = stats_r.json().get("seasons", [])
        if seasons:
            # Temporada más reciente
            s     = seasons[0]
            stats = s.get("statistics", {})
            lines.append(f"\n— Estadísticas temporada {s.get('year', 'actual')} —")
            for key, label in [
                ("appearances", "Partidos jugados"),
                ("goals", "Goles"),
                ("assists", "Asistencias"),
                ("minutesPlayed", "Minutos jugados"),
                ("yellowCards", "Tarjetas amarillas"),
                ("redCards", "Tarjetas rojas"),
                ("rating", "Rating promedio Sofascore"),
                ("successfulDribbles", "Regates exitosos"),
                ("keyPasses", "Pases clave"),
                ("tackles", "Entradas"),
                ("saves", "Atajadas"),  # porteros
                ("cleanSheets", "Vallas invictas"),
            ]:
                if key in stats and stats[key] is not None:
                    lines.append(f"{label}: {stats[key]}")

    # Últimos 5 partidos
    recent_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/events/last/0")
    if recent_r:
        events = recent_r.json().get("events", [])[:5]
        if events:
            lines.append("\n— Últimos partidos —")
            for ev in events:
                home = ev.get("homeTeam", {}).get("name", "?")
                away = ev.get("awayTeam", {}).get("name", "?")
                hs   = ev.get("homeScore", {}).get("current", "?")
                as_  = ev.get("awayScore", {}).get("current", "?")
                ts   = ev.get("startTimestamp")
                fecha = datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "?"
                lines.append(f"{fecha}: {home} {hs}-{as_} {away}")

    return "\n".join(lines)


def sofascore_player_historico(name: str) -> str:
    """Historial completo: clubes, títulos, stats de carrera, selección."""
    pid, p = _sofascore_player_id(name)
    if not pid:
        return ""

    lines = [f"JUGADOR: {p.get('name', name)}"]
    if p.get("position"):
        lines.append(f"Posición: {p['position']['name']}")
    if p.get("country"):
        lines.append(f"Nacionalidad: {p['country']['name']}")
    if p.get("dateOfBirthTimestamp"):
        dob = date.fromtimestamp(p["dateOfBirthTimestamp"])
        lines.append(f"Fecha de nacimiento: {dob}")

    # Historial de clubes y traspasos
    transfer_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/transfer/history")
    if transfer_r:
        transfers = transfer_r.json().get("transferHistory", [])
        if transfers:
            lines.append("\n— Historial de clubes —")
            for t in transfers:
                club  = t.get("team", {}).get("name", "?")
                desde = datetime.fromtimestamp(t["startTimestamp"]).strftime("%Y") if t.get("startTimestamp") else "?"
                hasta = datetime.fromtimestamp(t["endTimestamp"]).strftime("%Y") if t.get("endTimestamp") else "presente"
                fee   = t.get("transferFee")
                fee_str = f" · €{fee:,}" if fee else ""
                lines.append(f"{desde}–{hasta}: {club}{fee_str}")

    # Títulos y honores
    honors_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/honors")
    if honors_r:
        honors = honors_r.json().get("honors", [])
        if honors:
            lines.append("\n— Títulos y honores —")
            for h in honors:
                honor_name = h.get("honor", {}).get("name", "")
                seasons    = h.get("seasons", [])
                count      = len(seasons)
                seasons_str = ", ".join(seasons[:5])
                if count > 5:
                    seasons_str += f" (+{count-5} más)"
                lines.append(f"{honor_name} x{count}: {seasons_str}")

    # Stats de carrera (todas las temporadas)
    stats_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/statistics/season")
    if stats_r:
        seasons = stats_r.json().get("seasons", [])
        if seasons:
            # Totales acumulados de carrera
            total_partidos = sum(s.get("statistics", {}).get("appearances", 0) or 0 for s in seasons)
            total_goles    = sum(s.get("statistics", {}).get("goals", 0) or 0 for s in seasons)
            total_asist    = sum(s.get("statistics", {}).get("assists", 0) or 0 for s in seasons)
            total_min      = sum(s.get("statistics", {}).get("minutesPlayed", 0) or 0 for s in seasons)
            lines.append(f"\n— Totales de carrera (registrados en Sofascore) —")
            lines.append(f"Temporadas registradas: {len(seasons)}")
            if total_partidos: lines.append(f"Partidos totales: {total_partidos}")
            if total_goles:    lines.append(f"Goles totales: {total_goles}")
            if total_asist:    lines.append(f"Asistencias totales: {total_asist}")
            if total_min:      lines.append(f"Minutos totales: {total_min:,}")

            # Desglose por temporada (últimas 5)
            lines.append(f"\n— Desglose por temporada (más recientes) —")
            for s in seasons[:6]:
                st   = s.get("statistics", {})
                year = s.get("year", "?")
                team = s.get("team", {}).get("name", "?") if s.get("team") else "?"
                g    = st.get("goals", "-")
                a    = st.get("assists", "-")
                app  = st.get("appearances", "-")
                lines.append(f"{year} ({team}): {app} partidos · {g} goles · {a} asist.")

    # Stats selección nacional
    nat_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/national-team-statistics")
    if nat_r:
        nat = nat_r.json().get("statistics", [])
        if nat:
            lines.append("\n— Selección nacional —")
            for n in nat[:3]:
                team  = n.get("team", {}).get("name", "")
                stats = n.get("statistics", {})
                g     = stats.get("goals", "-")
                a     = stats.get("assists", "-")
                app   = stats.get("appearances", "-")
                lines.append(f"{team}: {app} partidos · {g} goles · {a} asist.")

    return "\n".join(lines)


def wikipedia_full(query: str) -> str:
    """Extrae el artículo completo de Wikipedia (más secciones que solo intro)."""
    search_url = (
        f"https://es.wikipedia.org/w/api.php"
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
    # Texto completo (no solo intro)
    extract_url = (
        f"https://es.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&explaintext=1"
        f"&titles={urllib.parse.quote_plus(title)}&format=json"
    )
    r2 = _get(extract_url)
    if not r2:
        return ""
    pages = r2.json().get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "")
        if not extract:
            return ""
        # Tomar los primeros 2500 caracteres (más que antes)
        paras = [p.strip() for p in extract.split("\n") if len(p.strip()) > 60]
        return "\n".join(paras[:20])[:2500]
    return ""


def _sofascore_team_id(name: str) -> tuple[int | None, dict]:
    search = _get(
        f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page=0"
    )
    if not search:
        return None, {}
    teams = search.json().get("teams", [])
    if not teams:
        return None, {}
    entity = teams[0]["entity"]
    return entity.get("id"), entity


def sofascore_team_temporada(name: str) -> str:
    """Temporada actual: stats, posición en tabla, últimos 5, próximos 5, entrenador."""
    tid, t = _sofascore_team_id(name)
    if not tid:
        return ""

    lines = [f"Equipo: {t.get('name', name)}"]
    if t.get("country"):
        lines.append(f"País: {t['country']['name']}")
    if t.get("tournament"):
        lines.append(f"Liga principal: {t['tournament']['name']}")

    # Entrenador
    manager_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/managers")
    if manager_r:
        managers = manager_r.json().get("managers", [])
        if managers:
            m = managers[0]
            lines.append(f"Entrenador: {m.get('name', '?')}")
            if m.get("country"):
                lines.append(f"Nacionalidad DT: {m['country']['name']}")

    # Últimos 5 partidos con fechas y resultado
    last_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/last/0")
    if last_r:
        events = last_r.json().get("events", [])[:5]
        if events:
            lines.append("\n— Últimos 5 partidos —")
            for ev in reversed(events):  # cronológico
                home_t = ev.get("homeTeam", {}).get("name", "?")
                away_t = ev.get("awayTeam", {}).get("name", "?")
                hs     = ev.get("homeScore", {}).get("current", "?")
                as_    = ev.get("awayScore", {}).get("current", "?")
                ts     = ev.get("startTimestamp")
                fecha  = datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "?"
                comp   = ev.get("tournament", {}).get("name", "")
                # Determinar W/D/L desde perspectiva del equipo consultado
                is_home = home_t == t.get("name", name) or name.lower() in home_t.lower()
                try:
                    hs_n, as_n = int(hs), int(as_)
                    if is_home:
                        wdl = "✓ G" if hs_n > as_n else ("= E" if hs_n == as_n else "✗ P")
                    else:
                        wdl = "✓ G" if as_n > hs_n else ("= E" if hs_n == as_n else "✗ P")
                except Exception:
                    wdl = ""
                lines.append(f"{fecha} [{wdl}] {home_t} {hs}-{as_} {away_t}  ({comp})")

    # Próximos 5 partidos
    next_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/next/0")
    if next_r:
        upcoming = next_r.json().get("events", [])[:5]
        if upcoming:
            lines.append("\n— Próximos 5 partidos —")
            for ev in upcoming:
                home_t = ev.get("homeTeam", {}).get("name", "?")
                away_t = ev.get("awayTeam", {}).get("name", "?")
                ts     = ev.get("startTimestamp")
                fecha  = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else "?"
                comp   = ev.get("tournament", {}).get("name", "")
                lines.append(f"{fecha}: {home_t} vs {away_t}  ({comp})")

    # Stats de temporada del equipo
    season_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/statistics/season/total")
    if not season_r:
        # Fallback: buscar via tournaments
        pass
    else:
        stats = season_r.json()
        if stats:
            lines.append("\n— Estadísticas de temporada —")
            for key, label in [
                ("wins", "Victorias"), ("draws", "Empates"), ("losses", "Derrotas"),
                ("goalsScored", "Goles a favor"), ("goalsConceded", "Goles en contra"),
                ("avgGoalsScored", "Promedio goles/partido"),
                ("cleanSheets", "Vallas invictas"),
            ]:
                if stats.get(key) is not None:
                    lines.append(f"{label}: {stats[key]}")

    return "\n".join(lines)


def sofascore_team_resultados(name: str) -> str:
    """Solo últimos 5 resultados con detalle."""
    tid, t = _sofascore_team_id(name)
    if not tid:
        return ""
    lines = [f"Equipo: {t.get('name', name)}"]
    last_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/last/0")
    if not last_r:
        return "\n".join(lines)
    events = last_r.json().get("events", [])[:5]
    lines.append("\n— Últimos 5 resultados —")
    for ev in reversed(events):
        home_t = ev.get("homeTeam", {}).get("name", "?")
        away_t = ev.get("awayTeam", {}).get("name", "?")
        hs     = ev.get("homeScore", {}).get("current", "?")
        as_    = ev.get("awayScore", {}).get("current", "?")
        ts     = ev.get("startTimestamp")
        fecha  = datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "?"
        comp   = ev.get("tournament", {}).get("name", "")
        lines.append(f"{fecha}: {home_t} {hs}-{as_} {away_t}  ({comp})")
    return "\n".join(lines)


def sofascore_team_proximos(name: str) -> str:
    """Solo próximos 5 partidos."""
    tid, t = _sofascore_team_id(name)
    if not tid:
        return ""
    lines = [f"Equipo: {t.get('name', name)}"]
    next_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/next/0")
    if not next_r:
        return "\n".join(lines)
    upcoming = next_r.json().get("events", [])[:5]
    lines.append("\n— Próximos 5 partidos —")
    for ev in upcoming:
        home_t = ev.get("homeTeam", {}).get("name", "?")
        away_t = ev.get("awayTeam", {}).get("name", "?")
        ts     = ev.get("startTimestamp")
        fecha  = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else "?"
        comp   = ev.get("tournament", {}).get("name", "")
        lines.append(f"{fecha}: {home_t} vs {away_t}  ({comp})")
    return "\n".join(lines)


def sofascore_coach(name: str) -> tuple[str, str]:
    """Devuelve (nombre_entrenador, manager_id) del equipo."""
    tid, _ = _sofascore_team_id(name)
    if not tid:
        return "", ""
    manager_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/managers")
    if not manager_r:
        return "", ""
    managers = manager_r.json().get("managers", [])
    if not managers:
        return "", ""
    m = managers[0]
    return m.get("name", ""), str(m.get("id", ""))


def sofascore_coach_historico(coach_name: str, coach_id: str) -> str:
    """Historial del entrenador: clubes dirigidos, títulos."""
    if not coach_id:
        return ""
    lines = [f"Entrenador: {coach_name}"]

    # Info básica
    info_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}")
    if info_r:
        data = info_r.json().get("manager", {})
        if data.get("country"):
            lines.append(f"Nacionalidad: {data['country']['name']}")
        if data.get("dateOfBirthTimestamp"):
            dob = date.fromtimestamp(data["dateOfBirthTimestamp"])
            age = (date.today() - dob).days // 365
            lines.append(f"Edad: {age} años")

    # Historial de equipos dirigidos
    history_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}/history")
    if history_r:
        history = history_r.json().get("managerHistory", [])
        if history:
            lines.append("\n— Equipos dirigidos —")
            for h in history[:10]:
                club  = h.get("team", {}).get("name", "?")
                desde = datetime.fromtimestamp(h["startTimestamp"]).strftime("%Y") if h.get("startTimestamp") else "?"
                hasta = datetime.fromtimestamp(h["endTimestamp"]).strftime("%Y") if h.get("endTimestamp") else "presente"
                lines.append(f"{desde}–{hasta}: {club}")

    # Títulos del DT
    honors_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}/honors")
    if honors_r:
        honors = honors_r.json().get("honors", [])
        if honors:
            lines.append("\n— Títulos como entrenador —")
            for h in honors[:8]:
                lines.append(f"• {h.get('honor',{}).get('name','?')} ({', '.join(h.get('seasons',[])[:3])})")

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
    tipo   = params["type"]
    fmt    = params.get("format", "")

    if tipo == "jugador":
        name = params["player"]

        # ── Según el formato pedido, priorizamos distinto tipo de dato ──
        if fmt in ("temporada", "cronica", "scouting", "tactico", "ficha", "lead", "tweet", "radio"):
            # Datos de temporada en curso
            sf = sofascore_player_temporada(name)
            if sf:
                parts.append(f"[SOFASCORE — TEMPORADA ACTUAL]\n{sf}")
                sources.append("Sofascore")
            # Noticias recientes
            snippets = ddg_snippets(f"{name} fútbol {año_actual()} estadísticas noticias temporada", 8)
            if snippets:
                parts.append("[NOTICIAS RECIENTES]\n" + "\n".join(
                    f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

        if fmt in ("historico", "perfil"):
            # Datos históricos completos
            sf_hist = sofascore_player_historico(name)
            if sf_hist:
                parts.append(f"[SOFASCORE — HISTÓRICO DE CARRERA]\n{sf_hist}")
                sources.append("Sofascore")
            # Wikipedia completo (más rico para historia personal)
            wiki = wikipedia_full(f"{name} futbolista")
            if not wiki:
                wiki = wikipedia_full(name)
            if wiki:
                parts.append(f"[WIKIPEDIA — CARRERA Y BIOGRAFÍA]\n{wiki}")
                sources.append("Wikipedia")
            snippets = ddg_snippets(f"{name} carrera trayectoria historia títulos", 6)
            if snippets:
                parts.append("[REFERENCIAS WEB]\n" + "\n".join(
                    f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

        if fmt == "scouting":
            # Para scouting también queremos algo de histórico
            sf_hist = sofascore_player_historico(name)
            if sf_hist and "[SOFASCORE — HISTÓRICO DE CARRERA]" not in "\n".join(parts):
                parts.append(f"[SOFASCORE — HISTÓRICO]\n{sf_hist}")

    elif tipo == "partido":
        home, away, comp = params["home"], params["away"], params.get("comp", "")
        sf = sofascore_match(home, away)
        if sf:
            parts.append(f"[SOFASCORE PARTIDO]\n{sf}"); sources.append("Sofascore")
        snippets = ddg_snippets(f"{home} vs {away} {comp} {año_actual()} resultado", 8)
        if snippets:
            parts.append("[NOTICIAS/RESULTADOS]\n" + "\n".join(
                f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    elif tipo == "equipo":
        name = params["team"]
        fmt  = params.get("format", "temporada")

        if fmt in ("temporada", "resultados", "proximos", "entrenador"):
            sf = sofascore_team_temporada(name)
            if sf:
                parts.append(f"[SOFASCORE — EQUIPO]\n{sf}"); sources.append("Sofascore")

        if fmt in ("entrenador", "dt_historico"):
            coach_name, coach_id = sofascore_coach(name)
            if coach_name:
                hist = sofascore_coach_historico(coach_name, coach_id)
                if hist:
                    parts.append(f"[SOFASCORE — ENTRENADOR]\n{hist}"); sources.append("Sofascore DT")
            # Wikipedia del entrenador
            if coach_name:
                wiki_dt = wikipedia_full(f"{coach_name} entrenador fútbol")
                if wiki_dt:
                    parts.append(f"[WIKIPEDIA — ENTRENADOR]\n{wiki_dt[:1000]}"); sources.append("Wikipedia")

        if fmt in ("temporada", "resultados", "proximos"):
            snippets = ddg_snippets(f"{name} fútbol {año_actual()} noticias temporada", 6)
            if snippets:
                parts.append("[NOTICIAS]\n" + "\n".join(
                    f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

    elif tipo == "libre":
        snippets = ddg_snippets(params.get("prompt", "") + f" fútbol {año_actual()}", 8)
        if snippets:
            parts.append("[BÚSQUEDA WEB]\n" + "\n".join(
                f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    return "\n\n".join(parts), sources


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS & GENERACIÓN
# ══════════════════════════════════════════════════════════════════════════════

FORMATS_PLAYER = {
    "temporada":  "un informe detallado de la temporada en curso: estadísticas actualizadas, rendimiento partido a partido, racha de forma, goles y asistencias, minutos jugados, rating promedio y proyección de cierre de temporada",
    "historico":  "un repaso histórico completo: trayectoria por clubes, títulos, estadísticas de carrera, hitos y récords personales, comparativa con grandes referentes de su posición y legado hasta hoy",
    "scouting":   "un scouting report profesional: perfil físico y técnico, sistema de juego ideal, fortalezas defensivas y ofensivas, debilidades a explotar, valoración de mercado y proyección futura",
    "tactico":    "un análisis táctico en profundidad: zonas de influencia, movimientos sin balón, pressing, transiciones, relación con compañeros, cómo condiciona el juego del equipo",
    "ficha":      "una ficha periodística completa (posición, club, estilo de juego, fortalezas, debilidades, momento actual, estadísticas recientes, dato destacado)",
    "perfil":     "un perfil biográfico humano (origen, infancia, carrera, hitos, personalidad, vida fuera del campo, legado)",
    "lead":       "un lead de apertura de nota (máximo 60 palabras, que enganche al lector desde la primera línea)",
    "tweet":      "un hilo de Twitter/X de 6 tweets numerados con emojis, pensado para viralizar",
    "radio":      "un texto de 90 segundos de radio, con ritmo oral y sin tecnicismos visuales",
    "cronica":    "una crónica de rendimiento reciente (forma actual, últimas actuaciones, estadísticas, perspectivas)",
}
FORMATS_MATCH = {
    "cronica":    "una crónica completa del partido",
    "prepartido": "una previa del partido (contexto, claves tácticas, jugadores a seguir, pronóstico)",
    "flash":      "un flash de resultado en exactamente 80 palabras",
    "analisis":   "un análisis táctico (sistemas, presión, transiciones, puntos de quiebre)",
    "tweet":      "un hilo de Twitter/X de 5-7 tweets numerados con emojis",
}
FORMATS_TEAM = {
    "temporada":   "un informe completo de la temporada actual: posición en tabla, estadísticas del equipo, racha de forma y análisis del momento",
    "resultados":  "una crónica de los últimos 5 resultados: qué pasó en cada partido, tendencias, rendimiento local/visitante y racha actual",
    "proximos":    "una previa de los próximos 5 partidos: rivales, contexto, dificultad de la agenda, claves tácticas y pronóstico",
    "entrenador":  "un perfil del entrenador actual: temporada en curso, sistema de juego, decisiones tácticas, rendimiento y vínculo con el plantel",
    "dt_historico":"un repaso histórico del entrenador: carrera como DT, clubes dirigidos, títulos, filosofía de juego y legado",
}


def build_prompt(p: dict, scraped_ctx: str) -> tuple[str, str]:
    fecha_hoy    = hoy()
    temporada    = temporada_vigente()

    sys_prompt = (
        "Sos un periodista deportivo argentino senior con 20 años de experiencia. "
        "Escribís para medios de primer nivel. Tu prosa es precisa, atractiva y refleja "
        "profundo conocimiento del deporte. Usás español rioplatense de forma natural.\n\n"
        "REGLAS ESTRICTAS ANTI-ALUCINACIÓN (son innegociables):\n"
        "1. SOLO usás estadísticas, fechas, resultados y cifras que aparezcan EXPLÍCITAMENTE "
        "en los datos scrapeados que te pasan. NUNCA inventés ni aproximés números.\n"
        "2. Si un dato no está en los datos provistos, escribís alrededor de él con criterio "
        "periodístico: describís el fenómeno, el impacto, el contexto, pero NO ponés números inventados.\n"
        "3. Si los datos son insuficientes para un punto específico, omitís ese punto. "
        "Prefierís un texto más corto y preciso que uno largo con datos falsos.\n"
        "4. Nunca usás frases como 'aproximadamente', 'alrededor de', 'se estima' para cifras "
        "deportivas. Si no sabés el número exacto, no lo ponés.\n"
        "5. Los datos scrapeados son la ÚNICA fuente de verdad para estadísticas. "
        "Tu conocimiento de entrenamiento puede usarse para CONTEXTO (comparaciones, análisis) "
        "pero NUNCA para estadísticas específicas como goles, partidos, fechas exactas.\n\n"
        f"CONTEXTO TEMPORAL:\n"
        f"- Fecha de hoy: {fecha_hoy}\n"
        f"- Temporada vigente: {temporada}\n"
        f"- Priorizá datos de la temporada en curso. Si los datos son de temporadas anteriores, "
        f"mencionalo claramente en el texto."
    )
    ctx_parts = []
    if scraped_ctx.strip():
        ctx_parts.append(
            f"═══ DATOS VERIFICADOS (scrapeados {fecha_hoy}) ═══\n"
            f"IMPORTANTE: Usá SOLO las estadísticas de esta sección. No agregues números de tu conocimiento.\n\n"
            f"{scraped_ctx}\n"
            f"═══ FIN DE DATOS VERIFICADOS ═══"
        )
    manual = p.get("context", "").strip()
    if manual:
        ctx_parts.append(f"DATOS ADICIONALES DEL PERIODISTA:\n{manual}")
    ctx_block = "\n\n".join(ctx_parts)

    tipo = p["type"]
    if tipo == "jugador":
        user = (
            f"Generá {FORMATS_PLAYER.get(p['format'], p['format'])} "
            f"sobre **{p['player']}**. "
            f"Enfocate en su estado actual y la temporada {temporada}."
        )
    elif tipo == "partido":
        score = f" (resultado: {p['score']})" if p.get("score") else ""
        user = (
            f"Generá {FORMATS_MATCH.get(p['format'], p['format'])} "
            f"del partido **{p['home']} vs {p['away']}**{score} · {p['comp']}. "
            f"Fecha de consulta: {fecha_hoy}."
        )
    elif tipo == "equipo":
        fmt_desc = FORMATS_TEAM.get(p["format"], p["format"])
        if p["format"] in ("entrenador", "dt_historico"):
            user = (
                f"Generá {fmt_desc} "
                f"del equipo **{p['team']}**. "
                f"Fecha: {fecha_hoy}. Usá los datos del entrenador scrapeados."
            )
        else:
            user = (
                f"Generá {fmt_desc} "
                f"sobre **{p['team']}**. "
                f"Enfocate en la temporada vigente ({temporada}) y el momento actual ({fecha_hoy})."
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
                model="claude-sonnet-4-5",
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
    fmt_player = st.selectbox(
        "Formato", list(FORMATS_PLAYER.keys()),
        format_func=lambda k: {
            "temporada": "📊 Datos de la temporada",
            "historico": "📖 Datos históricos / carrera",
            "scouting":  "🔍 Scouting report",
            "tactico":   "♟ Análisis táctico",
            "ficha":     "📋 Ficha completa",
            "perfil":    "👤 Perfil biográfico",
            "lead":      "✏️ Lead de nota",
            "tweet":     "🐦 Hilo Twitter/X",
            "radio":     "🎙 Texto para radio",
            "cronica":   "📰 Crónica de rendimiento",
        }[k], key="fmt_player",
    )
    ctx_player = st.text_area(
        "Datos extra (opcional)",
        placeholder="Stats propias, notas, contexto de la nota…",
        height=80, key="ctx_player",
    )
    if st.button("⚡ Generar", key="gen_jugador",
                 type="primary", use_container_width=True):
        if not player:
            st.warning("Ingresá el nombre del jugador.")
        else:
            generate(
                {"type": "jugador", "player": player, "format": fmt_player,
                 "context": ctx_player},
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
            "temporada":   "📊 Temporada actual",
            "resultados":  "📋 Últimos 5 resultados",
            "proximos":    "🗓 Próximos 5 partidos",
            "entrenador":  "🧢 Entrenador — temporada actual",
            "dt_historico":"📖 Entrenador — perfil histórico",
        }[k], key="fmt_team",
    )
    ctx_team = st.text_area(
        "Datos extra (opcional)",
        placeholder="Posición en tabla, bajas, refuerzos, contexto…",
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
