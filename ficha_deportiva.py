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


def get_tavily_key(user_input: str) -> str:
    if st.secrets.get("TAVILY_API_KEY"):
        return st.secrets["TAVILY_API_KEY"]
    return user_input.strip()


# Dominios de estadísticas deportivas verificadas — sin noticias, sin opinión
TAVILY_STATS_DOMAINS = [
    "sofascore.com",
    "fbref.com",
    "transfermarkt.com",
    "transfermarkt.es",
    "soccerstats.com",
    "whoscored.com",
    "fotmob.com",
    "livescore.com",
    "soccerway.com",
    "flashscore.com",
    "resultados-futbol.com",
    "bdfa.com.ar",           # Base de datos fútbol argentino
    "promiedos.com.ar",      # Tabla y stats Liga Argentina
    "livefutbol.com",
    "stats.com",
    "espn.com/soccer",
    "espndeportes.espn.com",
]


def tavily_search(query: str, tavily_key: str, max_results: int = 4) -> str:
    """
    Busca estadísticas deportivas via Tavily.
    Restringido a dominios de stats verificadas — sin noticias.
    """
    if not tavily_key:
        return ""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        resp = client.search(
            query=query,
            search_depth="advanced",
            include_domains=TAVILY_STATS_DOMAINS,
            max_results=max_results,
            include_answer=True,
        )
        lines = []
        if resp.get("answer"):
            lines.append(f"[Tavily síntesis]\n{resp['answer']}")
        for res in resp.get("results", [])[:max_results]:
            domain  = res.get("url", "").split("/")[2] if res.get("url") else ""
            content = (res.get("content") or "").strip()
            title   = res.get("title", "")
            if content:
                lines.append(f"[{domain}] {title}\n{content[:350]}")
        return "\n\n".join(lines)
    except Exception:
        return ""



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


def _name_words(name: str) -> set:
    """Palabras clave de un nombre, ignorando stopwords cortas."""
    stops = {"de", "del", "la", "el", "los", "las", "van", "von", "da", "di", "le", "fc", "cf", "sc", "ac"}
    return {w for w in name.lower().split() if w not in stops and len(w) > 2}


def _sofascore_player_id(name: str) -> tuple[int | None, dict]:
    """Busca jugador en Sofascore con matching estricto por nombre."""
    query_words = _name_words(name)
    best_score, best_entity = 0, {}

    for page in range(4):
        search = _get(
            f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page={page}"
        )
        if not search:
            break
        players = search.json().get("players", [])
        if not players:
            break
        for item in players:
            entity = item["entity"]
            entity_words = _name_words(entity.get("name", ""))
            shared = query_words & entity_words
            score  = len(shared)
            if entity.get("name", "").lower() == name.lower():
                return entity.get("id"), entity
            if score > best_score:
                best_score  = score
                best_entity = entity
        if best_score > 0:
            break

    if best_entity:
        return best_entity.get("id"), best_entity
    return None, {}


def _thesportsdb_player(name: str) -> dict:
    """TheSportsDB búsqueda de jugador — API gratuita."""
    r = _get(f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p={urllib.parse.quote_plus(name)}")
    if not r:
        return {}
    players = r.json().get("player") or []
    if not players:
        return {}
    query_words = _name_words(name)
    best_score, best = 0, players[0]
    for p in players:
        shared = query_words & _name_words(p.get("strPlayer", ""))
        if len(shared) > best_score:
            best_score = len(shared)
            best = p
    return best


def sofascore_player_temporada(name: str) -> str:
    """Stats temporada en curso. Capas: Sofascore → TheSportsDB → DDG."""
    pid, p = _sofascore_player_id(name)
    lines   = []

    if pid:
        lines.append(f"JUGADOR: {p.get('name', name)}")
        if p.get("position"):  lines.append(f"Posición: {p['position']['name']}")
        if p.get("team"):      lines.append(f"Club actual: {p['team']['name']}")
        if p.get("country"):   lines.append(f"Nacionalidad: {p['country']['name']}")
        if p.get("dateOfBirthTimestamp"):
            dob = date.fromtimestamp(p["dateOfBirthTimestamp"])
            age = (date.today() - dob).days // 365
            lines.append(f"Edad: {age} años ({dob})")
        if p.get("height"):         lines.append(f"Altura: {p['height']} cm")
        if p.get("preferredFoot"):  lines.append(f"Pie preferido: {p['preferredFoot']}")

        stats_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/statistics/season")
        if stats_r:
            seasons = stats_r.json().get("seasons", [])
            if seasons:
                s     = seasons[0]
                stats = s.get("statistics", {})
                team_s = s.get("team", {}).get("name", "?") if s.get("team") else "?"
                lines.append(f"\n— Estadísticas temporada {s.get('year', 'actual')} ({team_s}) —")
                for key, label in [
                    ("appearances",        "Partidos"),
                    ("goals",              "Goles"),
                    ("assists",            "Asistencias"),
                    ("minutesPlayed",      "Minutos"),
                    ("yellowCards",        "Amarillas"),
                    ("redCards",           "Rojas"),
                    ("rating",             "Rating Sofascore"),
                    ("successfulDribbles", "Regates"),
                    ("keyPasses",          "Pases clave"),
                    ("tackles",            "Entradas"),
                    ("saves",              "Atajadas"),
                    ("cleanSheets",        "Vallas invictas"),
                    ("goalConversionPercentage", "Conv. goles %"),
                ]:
                    if stats.get(key) is not None:
                        lines.append(f"{label}: {stats[key]}")

        last_events = []
        for page in range(3):
            ev_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/events/last/{page}")
            if not ev_r:
                break
            for ev in ev_r.json().get("events", []):
                if ev.get("homeScore", {}).get("current") is not None:
                    last_events.append(ev)
                if len(last_events) >= 5:
                    break
            if len(last_events) >= 5:
                break

        if last_events:
            lines.append("\n— Últimos partidos —")
            for ev in reversed(last_events):
                home  = ev.get("homeTeam", {}).get("name", "?")
                away  = ev.get("awayTeam", {}).get("name", "?")
                hs    = ev.get("homeScore", {}).get("current", "?")
                as_   = ev.get("awayScore", {}).get("current", "?")
                ts    = ev.get("startTimestamp")
                fecha = datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "?"
                comp  = ev.get("tournament", {}).get("name", "")
                lines.append(f"{fecha} | {home} {hs}-{as_} {away} | {comp}")

    if not pid:
        tsdb = _thesportsdb_player(name)
        if tsdb:
            lines.append(f"JUGADOR: {tsdb.get('strPlayer', name)}")
            if tsdb.get("strTeam"):        lines.append(f"Club actual: {tsdb['strTeam']}")
            if tsdb.get("strNationality"): lines.append(f"Nacionalidad: {tsdb['strNationality']}")
            if tsdb.get("strPosition"):    lines.append(f"Posición: {tsdb['strPosition']}")
            if tsdb.get("dateBorn"):       lines.append(f"Nacimiento: {tsdb['dateBorn']}")
            if tsdb.get("strHeight"):      lines.append(f"Altura: {tsdb['strHeight']}")

    if not lines:
        lines.append(f"JUGADOR: {name}")
        lines.append("[No encontrado en Sofascore ni TheSportsDB]")
        for s in ddg_snippets(f"{name} jugador fútbol estadísticas {año_actual()}", 5)[:4]:
            lines.append(f"• {s['title']}: {s['snippet'][:150]}")

    return "\n".join(lines)


def sofascore_player_historico(name: str) -> str:
    """Historial completo. Capas: Sofascore → TheSportsDB → Wikipedia."""
    pid, p = _sofascore_player_id(name)
    lines   = []

    if pid:
        lines.append(f"JUGADOR: {p.get('name', name)}")
        if p.get("position"):  lines.append(f"Posición: {p['position']['name']}")
        if p.get("country"):   lines.append(f"Nacionalidad: {p['country']['name']}")
        if p.get("dateOfBirthTimestamp"):
            dob = date.fromtimestamp(p["dateOfBirthTimestamp"])
            lines.append(f"Nacimiento: {dob}")

        tr_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/transfer/history")
        if tr_r:
            transfers = tr_r.json().get("transferHistory", [])
            if transfers:
                lines.append("\n— Historial de clubes —")
                for t in transfers:
                    club  = t.get("team", {}).get("name", "?")
                    desde = datetime.fromtimestamp(t["startTimestamp"]).strftime("%Y") if t.get("startTimestamp") else "?"
                    hasta = datetime.fromtimestamp(t["endTimestamp"]).strftime("%Y") if t.get("endTimestamp") else "presente"
                    fee   = t.get("transferFee")
                    fee_str = f" | €{fee:,}" if fee else ""
                    lines.append(f"{desde}–{hasta}: {club}{fee_str}")

        hon_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/honors")
        if hon_r:
            honors = hon_r.json().get("honors", [])
            if honors:
                lines.append("\n— Títulos —")
                for h in honors:
                    n_hon   = h.get("honor", {}).get("name", "")
                    seasons = h.get("seasons", [])
                    count   = len(seasons)
                    s_str   = ", ".join(seasons[:5])
                    if count > 5: s_str += f" (+{count-5})"
                    lines.append(f"{n_hon} x{count}: {s_str}")

        stats_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/statistics/season")
        if stats_r:
            seasons = stats_r.json().get("seasons", [])
            if seasons:
                tp = sum(s.get("statistics", {}).get("appearances", 0) or 0 for s in seasons)
                tg = sum(s.get("statistics", {}).get("goals", 0) or 0 for s in seasons)
                ta = sum(s.get("statistics", {}).get("assists", 0) or 0 for s in seasons)
                tm = sum(s.get("statistics", {}).get("minutesPlayed", 0) or 0 for s in seasons)
                lines.append(f"\n— Totales carrera ({len(seasons)} temporadas en Sofascore) —")
                if tp: lines.append(f"Partidos: {tp}")
                if tg: lines.append(f"Goles: {tg}")
                if ta: lines.append(f"Asistencias: {ta}")
                if tm: lines.append(f"Minutos: {tm:,}")
                lines.append("\n— Por temporada —")
                for s in seasons[:8]:
                    st   = s.get("statistics", {})
                    year = s.get("year", "?")
                    team = s.get("team", {}).get("name", "?") if s.get("team") else "?"
                    g    = st.get("goals", "-")
                    a    = st.get("assists", "-")
                    app  = st.get("appearances", "-")
                    rat  = st.get("rating", "")
                    lines.append(f"{year} ({team}): {app}pj · {g}g · {a}a" + (f" | {rat}" if rat else ""))

        nat_r = _get(f"https://api.sofascore.com/api/v1/player/{pid}/national-team-statistics")
        if nat_r:
            nat = nat_r.json().get("statistics", [])
            if nat:
                lines.append("\n— Selección nacional —")
                for n in nat[:3]:
                    team  = n.get("team", {}).get("name", "")
                    stats = n.get("statistics", {})
                    lines.append(f"{team}: {stats.get('appearances','-')}pj · {stats.get('goals','-')}g · {stats.get('assists','-')}a")

    if not pid:
        tsdb = _thesportsdb_player(name)
        if tsdb:
            lines.append(f"JUGADOR: {tsdb.get('strPlayer', name)}")
            for k, label in [("strTeam","Club"),("strNationality","Nacionalidad"),
                              ("strPosition","Posición"),("dateBorn","Nacimiento"),("strHeight","Altura")]:
                if tsdb.get(k): lines.append(f"{label}: {tsdb[k]}")
            if tsdb.get("strDescriptionEN"):
                lines.append(f"\nBiografía: {tsdb['strDescriptionEN'][:600]}")

    wiki = wikipedia_full(f"{name} futbolista") or wikipedia_full(name)
    if wiki:
        lines.append(f"\n— Wikipedia —\n{wiki}")

    return "\n".join(lines)


def wikipedia_full(query: str) -> str:
    """Artículo completo de Wikipedia en español."""
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
        paras = [p.strip() for p in extract.split("\n") if len(p.strip()) > 60]
        return "\n".join(paras[:20])[:2500]
    return ""


# ── TRANSFERMARKT API (wrapper no oficial, sin auth) ──────────────────────────
TM_BASE = "https://transfermarkt-api.vercel.app"


def _tm_search_player(name: str) -> tuple[str, str]:
    """Busca jugador en Transfermarkt. Devuelve (tm_id, nombre_oficial)."""
    r = _get(f"{TM_BASE}/players/search/{urllib.parse.quote_plus(name)}")
    if not r:
        return "", ""
    results = r.json().get("results", [])
    if not results:
        return "", ""
    query_words = _name_words(name)
    best_score, best = 0, results[0]
    for res in results:
        shared = query_words & _name_words(res.get("name", ""))
        if len(shared) > best_score:
            best_score = len(shared)
            best = res
    return str(best.get("id", "")), best.get("name", name)


def tm_player_profile(name: str) -> str:
    """
    Perfil completo del jugador en Transfermarkt:
    valor de mercado, historial de traspasos con montos, contrato.
    """
    tm_id, tm_name = _tm_search_player(name)
    if not tm_id:
        return ""

    lines = [f"[Transfermarkt] {tm_name}"]

    # Perfil básico + valor de mercado actual
    profile_r = _get(f"{TM_BASE}/players/{tm_id}/profile")
    if profile_r:
        d = profile_r.json()
        if d.get("marketValue"):
            lines.append(f"Valor de mercado: {d['marketValue']}")
        if d.get("club"):
            lines.append(f"Club: {d['club'].get('name','?')}")
        if d.get("citizenship"):
            lines.append(f"Ciudadanía: {', '.join(d['citizenship']) if isinstance(d['citizenship'], list) else d['citizenship']}")
        if d.get("dateOfBirth"):
            lines.append(f"Nacimiento: {d['dateOfBirth']}")
        if d.get("position"):
            lines.append(f"Posición: {d['position']}")
        if d.get("foot"):
            lines.append(f"Pie: {d['foot']}")
        if d.get("height"):
            lines.append(f"Altura: {d['height']}")
        if d.get("contractExpires"):
            lines.append(f"Contrato hasta: {d['contractExpires']}")
        if d.get("agent"):
            lines.append(f"Representante: {d['agent'].get('name','?')}")

    # Historial de valor de mercado (picos)
    mv_r = _get(f"{TM_BASE}/players/{tm_id}/market-value")
    if mv_r:
        history = mv_r.json().get("marketValueHistory", [])
        if history:
            # Valor máximo histórico
            try:
                peak = max(history, key=lambda x: float(str(x.get("value","0")).replace("€","").replace("M","").replace("k","0").replace(",",".") or 0))
                lines.append(f"Valor máximo histórico: {peak.get('value','?')} ({peak.get('date','?')})")
            except Exception:
                pass
            # Último valor registrado
            ultimo = history[-1]
            lines.append(f"Último valor registrado: {ultimo.get('value','?')} ({ultimo.get('date','?')})")

    # Historial de traspasos con montos
    tr_r = _get(f"{TM_BASE}/players/{tm_id}/transfers")
    if tr_r:
        transfers = tr_r.json().get("transfers", [])
        if transfers:
            lines.append("\n— Traspasos (Transfermarkt) —")
            for t in transfers[:10]:
                season = t.get("season", "?")
                from_c = t.get("from", {}).get("name", "?")
                to_c   = t.get("to", {}).get("name", "?")
                fee    = t.get("fee", "libre")
                mv_at  = t.get("marketValue", "")
                mv_str = f" (val. {mv_at})" if mv_at else ""
                lines.append(f"{season}: {from_c} → {to_c} | {fee}{mv_str}")

    return "\n".join(lines)


def tm_player_stats(name: str) -> str:
    """Stats por temporada de Transfermarkt (complementa Sofascore)."""
    tm_id, tm_name = _tm_search_player(name)
    if not tm_id:
        return ""
    stats_r = _get(f"{TM_BASE}/players/{tm_id}/stats")
    if not stats_r:
        return ""
    seasons = stats_r.json().get("stats", [])
    if not seasons:
        return ""
    lines = [f"[Transfermarkt] Stats por temporada — {tm_name}"]
    for s in seasons[:8]:
        comp    = s.get("competitionName", "?")
        club    = s.get("clubName", "?")
        season  = s.get("season", "?")
        apps    = s.get("appearances", "-")
        goals   = s.get("goals", "-")
        assists = s.get("assists", "-")
        mins    = s.get("minutesPlayed", "-")
        lines.append(f"{season} | {club} | {comp}: {apps}pj · {goals}g · {assists}a · {mins}min")
    return "\n".join(lines)


def _tm_search_club(name: str) -> tuple[str, str]:
    """Busca equipo en Transfermarkt. Devuelve (tm_id, nombre_oficial)."""
    r = _get(f"{TM_BASE}/clubs/search/{urllib.parse.quote_plus(name)}")
    if not r:
        return "", ""
    results = r.json().get("results", [])
    if not results:
        return "", ""
    query_words = _name_words(name)
    best_score, best = 0, results[0]
    for res in results:
        shared = query_words & _name_words(res.get("name", ""))
        if len(shared) > best_score:
            best_score = len(shared)
            best = res
    return str(best.get("id", "")), best.get("name", name)


def tm_club_profile(name: str) -> str:
    """
    Perfil del equipo en Transfermarkt:
    valor del plantel, entrenador, jugadores con valor de mercado.
    """
    tm_id, tm_name = _tm_search_club(name)
    if not tm_id:
        return ""

    lines = [f"[Transfermarkt] {tm_name}"]

    profile_r = _get(f"{TM_BASE}/clubs/{tm_id}/profile")
    if profile_r:
        d = profile_r.json()
        if d.get("squadMarketValue"):
            lines.append(f"Valor total del plantel: {d['squadMarketValue']}")
        if d.get("stadiumName"):
            lines.append(f"Estadio: {d['stadiumName']} (cap. {d.get('stadiumSeats','?')})")
        if d.get("leagueName"):
            lines.append(f"Liga: {d['leagueName']}")
        if d.get("squadSize"):
            lines.append(f"Plantel: {d['squadSize']} jugadores")
        if d.get("averageAge"):
            lines.append(f"Edad promedio: {d['averageAge']}")
        if d.get("foreignersNumber"):
            lines.append(f"Extranjeros: {d['foreignersNumber']}")

    # Top 5 jugadores por valor de mercado
    players_r = _get(f"{TM_BASE}/clubs/{tm_id}/players")
    if players_r:
        players = players_r.json().get("players", [])
        if players:
            lines.append("\n— Top jugadores por valor de mercado —")
            # Ordenar por valor (si está disponible)
            def parse_val(p):
                v = str(p.get("marketValue", "0")).replace("€","").replace("M","000000").replace("k","000").replace(",",".")
                try: return float(v)
                except: return 0
            top = sorted(players, key=parse_val, reverse=True)[:8]
            for p in top:
                pos = p.get("position", "?")
                nm  = p.get("name", "?")
                mv  = p.get("marketValue", "?")
                nat = p.get("nationality", "?")
                lines.append(f"{nm} ({pos}, {nat}): {mv}")

    return "\n".join(lines)


def _tm_search_coach(name: str) -> tuple[str, str]:
    """Busca entrenador en Transfermarkt."""
    r = _get(f"{TM_BASE}/coaches/search/{urllib.parse.quote_plus(name)}")
    if not r:
        return "", ""
    results = r.json().get("results", [])
    if not results:
        return "", ""
    query_words = _name_words(name)
    best_score, best = 0, results[0]
    for res in results:
        shared = query_words & _name_words(res.get("name", ""))
        if len(shared) > best_score:
            best_score = len(shared)
            best = res
    return str(best.get("id", "")), best.get("name", name)


def tm_coach_profile(name: str) -> str:
    """Perfil del entrenador en Transfermarkt: historial, valor planteles."""
    tm_id, tm_name = _tm_search_coach(name)
    if not tm_id:
        return ""
    lines = [f"[Transfermarkt] DT: {tm_name}"]
    profile_r = _get(f"{TM_BASE}/coaches/{tm_id}/profile")
    if profile_r:
        d = profile_r.json()
        if d.get("dateOfBirth"):    lines.append(f"Nacimiento: {d['dateOfBirth']}")
        if d.get("citizenship"):    lines.append(f"Ciudadanía: {d['citizenship']}")
        if d.get("currentClub"):    lines.append(f"Club actual: {d['currentClub'].get('name','?')}")
        if d.get("contractExpires"):lines.append(f"Contrato hasta: {d['contractExpires']}")
    history_r = _get(f"{TM_BASE}/coaches/{tm_id}/work-history")
    if history_r:
        history = history_r.json().get("workHistory", [])
        if history:
            lines.append("\n— Historial como DT (Transfermarkt) —")
            for h in history[:12]:
                club   = h.get("club", {}).get("name", "?")
                desde  = h.get("from", "?")
                hasta  = h.get("to", "presente")
                games  = h.get("games", "")
                wins   = h.get("wins", "")
                ratio  = h.get("winPercentage", "")
                detail = f" | {games}pj {wins}g {ratio}%" if games else ""
                lines.append(f"{desde}–{hasta}: {club}{detail}")
    return "\n".join(lines)


def _sofascore_team_id(name: str) -> tuple[int | None, dict]:
    """
    Busca el equipo en Sofascore con matching estricto por nombre.
    Nunca devuelve un equipo cuyo nombre no contenga alguna palabra del nombre buscado.
    """
    name_words = set(name.lower().split())

    for page in range(4):
        search = _get(
            f"https://api.sofascore.com/api/v1/search/multi-search?q={urllib.parse.quote_plus(name)}&page={page}"
        )
        if not search:
            break
        teams = search.json().get("teams", [])
        if not teams:
            break

        candidates = []
        for t in teams:
            entity      = t["entity"]
            entity_name = entity.get("name", "").lower()
            entity_words = set(entity_name.split())

            # Match exacto
            if entity_name == name.lower():
                return entity.get("id"), entity

            # Match parcial: al menos una palabra clave comparte
            shared = name_words & entity_words
            if shared:
                candidates.append((len(shared), entity))

        if candidates:
            # El que más palabras comparte
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][1].get("id"), candidates[0][1]

        # Si no hubo matches por palabras, no seguir buscando más páginas
        break

    return None, {}


def _sofascore_last_events(tid: int, team_name: str, needed: int = 5) -> list:
    """
    Pide hasta 4 páginas de eventos pasados.
    Filtra que el equipo con `tid` realmente aparezca en el partido.
    """
    events = []
    for page in range(4):
        r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/last/{page}")
        if not r:
            break
        batch = r.json().get("events", [])
        if not batch:
            break
        for e in batch:
            home_id = e.get("homeTeam", {}).get("id")
            away_id = e.get("awayTeam", {}).get("id")
            # Validar que el evento realmente pertenece a este equipo
            if home_id != tid and away_id != tid:
                continue
            # Solo partidos con resultado
            if e.get("homeScore", {}).get("current") is None:
                continue
            events.append(e)
            if len(events) >= needed:
                break
        if len(events) >= needed:
            break
    return events[:needed]


def _sofascore_next_events(tid: int, needed: int = 5) -> list:
    """Próximos eventos, filtrando que tid realmente participe."""
    events = []
    for page in range(3):
        r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/events/next/{page}")
        if not r:
            break
        batch = r.json().get("events", [])
        if not batch:
            break
        for e in batch:
            home_id = e.get("homeTeam", {}).get("id")
            away_id = e.get("awayTeam", {}).get("id")
            if home_id == tid or away_id == tid:
                events.append(e)
            if len(events) >= needed:
                break
        if len(events) >= needed:
            break
    return events[:needed]


def _web_scrape_results(team_name: str) -> tuple[list[str], list[str]]:
    """
    Scrapea resultados y próximos partidos directamente desde snippets de DuckDuckGo.
    Busca patrones de marcador reales en los snippets.
    Retorna (últimos_resultados, próximos_partidos) como listas de strings.
    """
    import re
    last_lines, next_lines = [], []

    # Búsqueda específica de resultados
    snippets_res = ddg_snippets(f"{team_name} resultados últimos partidos {año_actual()}", 10)
    snippets_prox = ddg_snippets(f"{team_name} próximos partidos fixture {año_actual()}", 6)

    score_pattern = re.compile(r'([A-Za-záéíóúÁÉÍÓÚñÑ\s\.]+?)\s+(\d+)\s*[-–]\s*(\d+)\s+([A-Za-záéíóúÁÉÍÓÚñÑ\s\.]+)')

    seen = set()
    for s in snippets_res:
        text = s.get("snippet", "") + " " + s.get("title", "")
        for m in score_pattern.finditer(text):
            h, hs, as_, a = m.group(1).strip(), m.group(2), m.group(3), m.group(4).strip()
            # Filtrar resultados irrelevantes (muy cortos o sin palabras reales)
            if len(h) < 3 or len(a) < 3:
                continue
            line = f"{h} {hs}-{as_} {a}"
            if line not in seen:
                seen.add(line)
                last_lines.append(line)
            if len(last_lines) >= 5:
                break
        if len(last_lines) >= 5:
            break

    # Próximos: buscar patrones de fecha + equipos en snippets
    date_pattern = re.compile(r'(\d{1,2}/\d{1,2}|\d{1,2} de \w+)[^a-zA-Z]*([A-Za-záéíóúÁÉÍÓÚñÑ\s]+)\s+vs\.?\s+([A-Za-záéíóúÁÉÍÓÚñÑ\s]+)')
    seen_next = set()
    for s in snippets_prox:
        text = s.get("snippet", "") + " " + s.get("title", "")
        for m in date_pattern.finditer(text):
            fecha, h, a = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if len(h) < 3 or len(a) < 3:
                continue
            line = f"{fecha}: {h} vs {a}"
            if line not in seen_next:
                seen_next.add(line)
                next_lines.append(line)
            if len(next_lines) >= 5:
                break
        if len(next_lines) >= 5:
            break

    return last_lines, next_lines


def _thesportsdb_team(name: str) -> dict:
    """TheSportsDB — API gratuita, sin key."""
    r = _get(f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={urllib.parse.quote_plus(name)}")
    if not r:
        return {}
    teams = r.json().get("teams") or []
    if not teams:
        return {}
    for t in teams:
        if t.get("strTeam", "").lower() == name.lower():
            return t
    return teams[0]


def _thesportsdb_team_events(tsdb_id: str) -> tuple[list, list]:
    last, nxt = [], []
    r_last = _get(f"https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id={tsdb_id}")
    if r_last:
        last = (r_last.json().get("results") or [])[:5]
    r_next = _get(f"https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id={tsdb_id}")
    if r_next:
        nxt = (r_next.json().get("events") or [])[:5]
    return last, nxt


def _format_events_sofascore(events: list, team_id: int, mode: str = "last") -> list[str]:
    lines = []
    iterable = list(reversed(events)) if mode == "last" else events
    for ev in iterable:
        home_t  = ev.get("homeTeam", {}).get("name", "?")
        away_t  = ev.get("awayTeam", {}).get("name", "?")
        home_id = ev.get("homeTeam", {}).get("id")
        hs      = ev.get("homeScore", {}).get("current", "?")
        as_     = ev.get("awayScore", {}).get("current", "?")
        ts      = ev.get("startTimestamp")
        fecha   = datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "?"
        comp    = ev.get("tournament", {}).get("name", "")
        if mode == "last":
            is_home = home_id == team_id
            try:
                hs_n, as_n = int(hs), int(as_)
                wdl = ("G" if (is_home and hs_n > as_n) or (not is_home and as_n > hs_n)
                       else ("E" if hs_n == as_n else "P"))
            except Exception:
                wdl = "-"
            lines.append(f"{fecha} | {wdl} | {home_t} {hs}-{as_} {away_t} | {comp}")
        else:
            hora = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
            lines.append(f"{fecha} {hora} | {home_t} vs {away_t} | {comp}")
    return lines


def _format_events_tsdb(events: list, mode: str = "last") -> list[str]:
    lines = []
    for ev in events:
        fecha  = ev.get("dateEvent", "?")
        hora   = ev.get("strTime", "")
        home_t = ev.get("strHomeTeam", "?")
        away_t = ev.get("strAwayTeam", "?")
        comp   = ev.get("strLeague", "")
        if mode == "last":
            hs  = ev.get("intHomeScore", "?")
            as_ = ev.get("intAwayScore", "?")
            lines.append(f"{fecha} | {home_t} {hs}-{as_} {away_t} | {comp}")
        else:
            lines.append(f"{fecha} {hora} | {home_t} vs {away_t} | {comp}")
    return lines


def sofascore_team_temporada(name: str) -> str:
    """
    Datos duros de la temporada actual.
    Capas: Sofascore (con validación estricta de ID) → TheSportsDB → web scraping DDG.
    """
    lines = []
    team_display = name
    tid, t = _sofascore_team_id(name)

    sf_last, sf_next = [], []
    if tid:
        team_display = t.get("name", name)
        lines.append(f"Equipo: {team_display}")
        if t.get("country"):
            lines.append(f"País: {t['country']['name']}")
        if t.get("tournament"):
            lines.append(f"Liga: {t['tournament']['name']}")

        mgr_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/managers")
        if mgr_r:
            mgrs = mgr_r.json().get("managers", [])
            if mgrs:
                lines.append(f"Entrenador: {mgrs[0].get('name','?')}")

        # Posición en tabla
        stand_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/standings/last")
        if stand_r:
            for sg in stand_r.json().get("standings", [])[:1]:
                for row in sg.get("rows", []):
                    if row.get("team", {}).get("id") == tid:
                        p = row
                        lines.append(
                            f"\n— Tabla ({sg.get('name','Liga')}) —\n"
                            f"Pos: {p.get('position','?')} | "
                            f"PJ: {p.get('matches','?')} | "
                            f"G-E-P: {p.get('wins','?')}-{p.get('draws','?')}-{p.get('losses','?')} | "
                            f"GF: {p.get('scoresFor','?')} GC: {p.get('scoresAgainst','?')} | "
                            f"Pts: {p.get('points','?')}"
                        )
                        break

        sf_last = _sofascore_last_events(tid, team_display, 5)
        sf_next = _sofascore_next_events(tid, 5)

    # TheSportsDB como segunda capa
    tsdb = _thesportsdb_team(name)
    tsdb_last, tsdb_next = [], []
    if tsdb:
        if not lines:
            lines.append(f"Equipo: {tsdb.get('strTeam', name)}")
            if tsdb.get("strCountry"): lines.append(f"País: {tsdb['strCountry']}")
            if tsdb.get("strLeague"):  lines.append(f"Liga: {tsdb['strLeague']}")
            if tsdb.get("strManager"): lines.append(f"Entrenador: {tsdb['strManager']}")
        tsdb_id = tsdb.get("idTeam", "")
        if tsdb_id:
            tsdb_last, tsdb_next = _thesportsdb_team_events(tsdb_id)

    # ── Últimos 5: Sofascore → TSDB → web ──
    if sf_last:
        last_lines = _format_events_sofascore(sf_last, tid or 0)
    elif tsdb_last:
        last_lines = _format_events_tsdb(tsdb_last)
    else:
        # Tercera capa: DDG snippets con extracción de marcadores
        web_last, _ = _web_scrape_results(name)
        last_lines = web_last

    if last_lines:
        lines.append("\n— Últimos 5 partidos (fecha | G/E/P | marcador | competencia) —")
        lines.extend(last_lines)
    else:
        lines.append(f"\n[Últimos partidos de {name}: no encontrados — intentar buscar en ESPN o Sofascore manualmente]")

    # ── Próximos 5: Sofascore → TSDB → web ──
    if sf_next:
        next_lines = _format_events_sofascore(sf_next, tid or 0, "next")
    elif tsdb_next:
        next_lines = _format_events_tsdb(tsdb_next, "next")
    else:
        _, web_next = _web_scrape_results(name)
        next_lines = web_next

    if next_lines:
        lines.append("\n— Próximos 5 partidos (fecha | hora | rival | competencia) —")
        lines.extend(next_lines)
    else:
        lines.append(f"\n[Próximos partidos de {name}: no encontrados]")

    return "\n".join(lines)


def sofascore_coach(name: str) -> tuple[str, str]:
    """Devuelve (nombre_entrenador, manager_id) del equipo."""
    tid, _ = _sofascore_team_id(name)
    if not tid:
        # Fallback TheSportsDB
        tsdb = _thesportsdb_team(name)
        return tsdb.get("strManager", ""), ""
    mgr_r = _get(f"https://api.sofascore.com/api/v1/team/{tid}/managers")
    if not mgr_r:
        return "", ""
    managers = mgr_r.json().get("managers", [])
    if not managers:
        return "", ""
    m = managers[0]
    return m.get("name", ""), str(m.get("id", ""))


def sofascore_coach_historico(coach_name: str, coach_id: str, team_name: str = "") -> str:
    """
    Historial del entrenador.
    Capa 1: Sofascore. Capa 2: TheSportsDB. Capa 3: Wikipedia.
    """
    if not coach_name:
        return ""
    lines = [f"Entrenador: {coach_name}"]

    if coach_id:
        info_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}")
        if info_r:
            data = info_r.json().get("manager", {})
            if data.get("country"):
                lines.append(f"Nacionalidad: {data['country']['name']}")
            if data.get("dateOfBirthTimestamp"):
                dob = date.fromtimestamp(data["dateOfBirthTimestamp"])
                age = (date.today() - dob).days // 365
                lines.append(f"Edad: {age} años ({dob})")
            if data.get("preferredFormation"):
                lines.append(f"Formación preferida: {data['preferredFormation']}")

        hist_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}/history")
        if hist_r:
            history = hist_r.json().get("managerHistory", [])
            if history:
                lines.append("\n— Clubes dirigidos —")
                for h in history[:12]:
                    club  = h.get("team", {}).get("name", "?")
                    desde = datetime.fromtimestamp(h["startTimestamp"]).strftime("%d/%m/%Y") if h.get("startTimestamp") else "?"
                    hasta = datetime.fromtimestamp(h["endTimestamp"]).strftime("%d/%m/%Y") if h.get("endTimestamp") else "presente"
                    lines.append(f"{desde} → {hasta}: {club}")

        hon_r = _get(f"https://api.sofascore.com/api/v1/manager/{coach_id}/honors")
        if hon_r:
            honors = hon_r.json().get("honors", [])
            if honors:
                lines.append("\n— Títulos como DT —")
                for h in honors[:10]:
                    title   = h.get("honor", {}).get("name", "?")
                    seasons = ", ".join(h.get("seasons", [])[:4])
                    count   = len(h.get("seasons", []))
                    lines.append(f"• {title} x{count}: {seasons}")

    tsdb_r = _get(f"https://www.thesportsdb.com/api/v1/json/3/searchmanagers.php?m={urllib.parse.quote_plus(coach_name)}")
    if tsdb_r:
        managers = tsdb_r.json().get("managers") or []
        if managers:
            best_m = managers[0]
            for m in managers:
                if _name_words(m.get("strManager","")) & _name_words(coach_name):
                    best_m = m
                    break
            m = best_m
            if not coach_id:
                for k, label in [("strNationality","Nacionalidad"),("dateBorn","Nacimiento"),("strTeam","Club actual")]:
                    if m.get(k): lines.append(f"{label}: {m[k]}")
            if m.get("strDescriptionEN") and len(lines) < 6:
                lines.append(f"\nBiografía (TheSportsDB): {m['strDescriptionEN'][:500]}")

    wiki = wikipedia_full(f"{coach_name} entrenador fútbol") or wikipedia_full(coach_name)
    if wiki:
        lines.append(f"\n— Wikipedia —\n{wiki[:1500]}")

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


def _tavily_for_params(params: dict, tavily_key: str) -> str:
    """
    Construye la query de Tavily según el tipo de búsqueda.
    Solo dominios de estadísticas — sin noticias.
    """
    tipo = params["type"]
    fmt  = params.get("format", "")

    if tipo == "jugador":
        name = params["player"]
        if fmt in ("temporada", "cronica", "ficha", "scouting", "tactico"):
            query = f"{name} estadísticas temporada 2024 2025 goles asistencias partidos"
        elif fmt in ("historico", "perfil"):
            query = f"{name} carrera estadísticas históricas clubes transferencias"
        else:
            query = f"{name} estadísticas fútbol"

    elif tipo == "equipo":
        name = params["team"]
        if fmt == "temporada":
            query = f"{name} tabla posiciones estadísticas temporada 2024 2025"
        elif fmt == "resultados":
            query = f"{name} últimos resultados partidos marcadores 2025"
        elif fmt == "proximos":
            query = f"{name} próximos partidos fixture 2025"
        elif fmt in ("entrenador", "dt_historico"):
            query = f"{name} entrenador estadísticas partidos dirigidos"
        else:
            query = f"{name} estadísticas fútbol 2025"

    elif tipo == "partido":
        query = f"{params['home']} vs {params['away']} estadísticas resultado"

    else:
        query = params.get("prompt", "")

    if not query:
        return ""

    return tavily_search(query, tavily_key, max_results=4)


def scrape_context(params: dict) -> tuple[str, list[str]]:
    parts, sources = [], []
    tipo = params["type"]
    fmt  = params.get("format", "")

    # ── JUGADOR ──────────────────────────────────────────────────────────────
    if tipo == "jugador":
        name = params["player"]

        if fmt in ("temporada", "cronica", "scouting", "tactico", "ficha", "lead", "tweet", "radio"):
            sf = sofascore_player_temporada(name)
            if sf:
                parts.append(f"[SOFASCORE — TEMPORADA]\n{sf}"); sources.append("Sofascore")

            # Transfermarkt: valor de mercado + contrato (útil en temporada y scouting)
            tm = tm_player_profile(name)
            if tm:
                parts.append(f"[TRANSFERMARKT]\n{tm}"); sources.append("Transfermarkt")

            snippets = ddg_snippets(f"{name} fútbol {año_actual()} estadísticas noticias temporada", 6)
            if snippets:
                parts.append("[NOTICIAS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

        if fmt in ("historico", "perfil"):
            sf_hist = sofascore_player_historico(name)
            if sf_hist:
                parts.append(f"[SOFASCORE — HISTÓRICO]\n{sf_hist}"); sources.append("Sofascore")

            # Transfermarkt: historial de traspasos con montos + valor histórico
            tm = tm_player_profile(name)
            if tm:
                parts.append(f"[TRANSFERMARKT]\n{tm}"); sources.append("Transfermarkt")

            snippets = ddg_snippets(f"{name} carrera trayectoria historia títulos", 6)
            if snippets:
                parts.append("[REFERENCIAS WEB]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

        if fmt == "scouting":
            sf_hist = sofascore_player_historico(name)
            if sf_hist and "[SOFASCORE — HISTÓRICO]" not in "\n".join(parts):
                parts.append(f"[SOFASCORE — HISTÓRICO]\n{sf_hist}"); sources.append("Sofascore hist.")
            # Stats por temporada de TM (complementa scouting)
            tm_stats = tm_player_stats(name)
            if tm_stats and "[TRANSFERMARKT]" not in "\n".join(parts):
                parts.append(f"[TRANSFERMARKT — STATS]\n{tm_stats}"); sources.append("Transfermarkt")

    # ── PARTIDO ──────────────────────────────────────────────────────────────
    elif tipo == "partido":
        home, away, comp = params["home"], params["away"], params.get("comp", "")
        sf = sofascore_match(home, away)
        if sf:
            parts.append(f"[SOFASCORE PARTIDO]\n{sf}"); sources.append("Sofascore")
        snippets = ddg_snippets(f"{home} vs {away} {comp} {año_actual()} resultado", 8)
        if snippets:
            parts.append("[NOTICIAS/RESULTADOS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    # ── EQUIPO ───────────────────────────────────────────────────────────────
    elif tipo == "equipo":
        name = params["team"]
        fmt  = params.get("format", "temporada")

        if fmt in ("temporada", "resultados", "proximos", "entrenador"):
            sf = sofascore_team_temporada(name)
            if sf:
                parts.append(f"[SOFASCORE — EQUIPO]\n{sf}"); sources.append("Sofascore")

            # Transfermarkt: valor del plantel, top jugadores
            tm = tm_club_profile(name)
            if tm:
                parts.append(f"[TRANSFERMARKT — PLANTEL]\n{tm}"); sources.append("Transfermarkt")

        if fmt in ("entrenador", "dt_historico"):
            coach_name, coach_id = sofascore_coach(name)
            if coach_name:
                hist = sofascore_coach_historico(coach_name, coach_id, name)
                if hist:
                    parts.append(f"[SOFASCORE — ENTRENADOR]\n{hist}"); sources.append("Sofascore DT")
                # Transfermarkt del entrenador (historial, win ratio)
                tm_dt = tm_coach_profile(coach_name)
                if tm_dt:
                    parts.append(f"[TRANSFERMARKT — DT]\n{tm_dt}"); sources.append("Transfermarkt DT")
                wiki_dt = wikipedia_full(f"{coach_name} entrenador fútbol")
                if wiki_dt:
                    parts.append(f"[WIKIPEDIA — ENTRENADOR]\n{wiki_dt[:1000]}"); sources.append("Wikipedia")

        if fmt in ("temporada", "resultados", "proximos"):
            snippets = ddg_snippets(f"{name} fútbol {año_actual()} noticias temporada", 6)
            if snippets:
                parts.append("[NOTICIAS]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
                sources.append("DuckDuckGo")

    # ── LIBRE ─────────────────────────────────────────────────────────────────
    elif tipo == "libre":
        snippets = ddg_snippets(params.get("prompt", "") + f" fútbol {año_actual()}", 8)
        if snippets:
            parts.append("[BÚSQUEDA WEB]\n" + "\n".join(f"• {s['title']}: {s['snippet']}" for s in snippets))
            sources.append("DuckDuckGo")

    return "\n\n".join(parts), sources



# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS & GENERACIÓN
# ══════════════════════════════════════════════════════════════════════════════

FORMATS_PLAYER = {
    "temporada": "ficha de temporada",
    "historico": "ficha histórica",
    "scouting":  "scouting report",
    "tactico":   "análisis táctico",
    "ficha":     "ficha completa",
    "perfil":    "perfil biográfico",
    "lead":      "lead de nota (máx 60 palabras)",
    "tweet":     "hilo Twitter/X (6 tweets con emojis)",
    "radio":     "texto radio (90 segundos)",
    "cronica":   "crónica de rendimiento",
}
FORMATS_MATCH = {
    "cronica":    "crónica del partido",
    "prepartido": "previa del partido",
    "flash":      "flash de resultado (80 palabras exactas)",
    "analisis":   "análisis táctico",
    "tweet":      "hilo Twitter/X (5-7 tweets)",
}
FORMATS_TEAM = {
    "temporada":   "ficha de temporada",
    "resultados":  "reporte de últimos 5 resultados",
    "proximos":    "agenda de próximos 5 partidos",
    "entrenador":  "ficha del entrenador (temporada actual)",
    "dt_historico":"ficha histórica del entrenador",
}

FORMAT_INSTRUCTIONS = {
    "temporada": (
        "Producí una FICHA DE TEMPORADA con esta estructura exacta:\n"
        "**[Nombre] — Temporada [año]**\n"
        "Club: | Posición: | Edad:\n"
        "Partidos: | Goles: | Asistencias: | Minutos: | Rating:\n"
        "Últimos 5 partidos: (lista)\n"
        "Valor de mercado: | Contrato hasta:\n"
        "Análisis: (2 líneas máximo, solo si los datos lo justifican)\n\n"
        "REGLA: Completá solo campos con datos verificados. Sin dato → 'n/d'. NO inventes."
    ),
    "historico": (
        "Producí una FICHA HISTÓRICA con esta estructura exacta:\n"
        "**[Nombre] — Carrera**\n"
        "Nacimiento: | Nacionalidad: | Posición:\n"
        "Clubes: (lista cronológica con años)\n"
        "Estadísticas carrera: Partidos: | Goles: | Asistencias:\n"
        "Selección: Partidos: | Goles: | Títulos:\n"
        "Palmarés: (lista con año)\n"
        "Valor pico: | Valor actual:\n\n"
        "REGLA: Solo datos verificados. Sin dato → 'n/d'. Máximo 250 palabras."
    ),
    "scouting": (
        "Producí un SCOUTING REPORT con esta estructura:\n"
        "**[Nombre] — Scouting**\n"
        "Posición: | Edad: | Pie: | Altura: | Valor: | Contrato:\n"
        "Stats temporada actual: (lista breve)\n"
        "Fortalezas: (3 puntos con datos)\n"
        "Debilidades: (2 puntos con datos)\n"
        "Veredicto: (1 línea)\n\n"
        "REGLA: Solo afirmaciones con datos. Máximo 200 palabras."
    ),
    "tactico": (
        "Producí un ANÁLISIS TÁCTICO de máximo 120 palabras.\n"
        "Estructura: posición → zonas → movimientos clave → impacto en equipo.\n"
        "Solo datos provistos. Sin generalidades."
    ),
    "ficha": (
        "Producí una FICHA en formato compacto:\n"
        "**[Nombre]** | [Club] | [Posición]\n"
        "Stats clave + valor + contrato + 1 dato destacado.\n"
        "Máximo 80 palabras. Solo datos verificados."
    ),
    "perfil": (
        "Producí un PERFIL BIOGRÁFICO de máximo 180 palabras.\n"
        "Estructura: origen → carrera → hito → momento actual.\n"
        "Solo hechos verificables. No inventes anécdotas."
    ),
    "lead": "Escribí un LEAD de 50-60 palabras exactas. Solo datos reales provistos.",
    "tweet": "Escribí 6 TWEETS numerados con emojis. Máx 280 caracteres c/u. Solo datos reales.",
    "radio": "Escribí TEXTO RADIO de ≈180 palabras (90 segundos). Ritmo oral. Solo datos reales.",
    "cronica": (
        "Producí una CRÓNICA DE RENDIMIENTO de máximo 130 palabras.\n"
        "Estructura: forma actual → últimas actuaciones → stats → perspectiva.\n"
        "Solo datos verificados."
    ),
    "resultados": (
        "Producí un REPORTE DE RESULTADOS:\n"
        "**[Equipo] — Últimos 5 partidos**\n"
        "(lista: fecha | G/E/P | marcador | rival | competencia)\n"
        "Balance: G: E: P: GF: GC:\n"
        "Racha: (1 línea)\n\n"
        "REGLA: Solo los datos que tenés. Sin datos → indicalo."
    ),
    "proximos": (
        "Producí una AGENDA DE PARTIDOS:\n"
        "**[Equipo] — Próximos partidos**\n"
        "(lista: fecha | hora | local vs visitante | competencia)\n"
        "Partido clave: (1 línea sobre el más importante)\n\n"
        "REGLA: Solo los datos que tenés."
    ),
    "temporada_equipo": (
        "Producí una FICHA DE TEMPORADA DEL EQUIPO:\n"
        "**[Equipo] — Temporada [año]**\n"
        "Liga: | Entrenador: | Pos en tabla:\n"
        "PJ: | G: | E: | P: | GF: | GC: | Pts:\n"
        "Valor del plantel:\n"
        "Últimos 5: (lista breve)\n"
        "Próximos 2: (lista breve)\n"
        "Análisis: (2 líneas máximo)\n\n"
        "REGLA: Solo datos verificados. Máximo 200 palabras."
    ),
    "entrenador": (
        "Producí una FICHA DEL ENTRENADOR:\n"
        "**[Nombre] — [Club]**\n"
        "Nacionalidad: | Edad: | En el club desde:\n"
        "Temporada: PJ: | G: | E: | P: | % victorias:\n"
        "Sistema: | Estilo:\n"
        "Análisis: (2 líneas con datos)\n\n"
        "REGLA: Solo datos verificados. Máximo 150 palabras."
    ),
    "dt_historico": (
        "Producí una FICHA HISTÓRICA DEL DT:\n"
        "**[Nombre] — Carrera como DT**\n"
        "Nacionalidad: | Edad:\n"
        "Clubes: (lista cronológica con años y win%)\n"
        "Títulos: (lista)\n"
        "Análisis: (2 líneas)\n\n"
        "REGLA: Solo datos verificados. Máximo 200 palabras."
    ),
}


def build_prompt(p: dict, scraped_ctx: str) -> tuple[str, str]:
    fecha_hoy = hoy()
    temporada = temporada_vigente()

    sys_prompt = (
        "Sos un periodista deportivo argentino. Respondés BREVE y ESTRUCTURADO.\n\n"
        "REGLAS (innegociables):\n"
        "1. Usá SOLO los datos del bloque DATOS VERIFICADOS para estadísticas y cifras.\n"
        "2. Sin dato verificado → escribí 'n/d'. NUNCA inventes ni rellenes.\n"
        "3. Preferís corto y preciso. Sin prosa vacía.\n"
        "4. Menos datos = output más corto, no más largo.\n"
        "5. Nunca: 'se estima', 'aproximadamente', 'según fuentes'.\n\n"
        f"Fecha: {fecha_hoy} | Temporada: {temporada}"
    )

    ctx_block = ""
    if scraped_ctx.strip():
        ctx_block = f"═══ DATOS VERIFICADOS ═══\n{scraped_ctx}\n═══ FIN ═══"
    manual = p.get("context", "").strip()
    if manual:
        ctx_block += f"\n\nDATOS EXTRA DEL PERIODISTA:\n{manual}"

    tipo = p["type"]
    fmt  = p.get("format", "")
    fmt_key = "temporada_equipo" if (tipo == "equipo" and fmt == "temporada") else fmt

    instruccion = FORMAT_INSTRUCTIONS.get(fmt_key, f"Generá una {fmt} breve con datos.")

    if tipo == "jugador":
        subject = f"JUGADOR: {p['player']}"
    elif tipo == "partido":
        score = f" (resultado: {p['score']})" if p.get("score") else ""
        subject = f"PARTIDO: {p['home']} vs {p['away']}{score} — {p['comp']}"
    elif tipo == "equipo":
        subject = f"EQUIPO: {p['team']}"
    else:
        subject = ""

    if ctx_block:
        user = f"{instruccion}\n\n{subject}\n\n{ctx_block}"
    else:
        user = f"{instruccion}\n\n{subject}\n\n[Sin datos scrapeados — indicá qué falta]"

    return sys_prompt, user



def get_label(p: dict) -> str:
    if p["type"] == "jugador": return f"{p['player']} · {p['format']}"
    if p["type"] == "partido": return f"{p['home']} vs {p['away']}"
    if p["type"] == "equipo":  return f"{p['team']} · {p['format']}"
    return (p.get("prompt") or "")[:45] + "…"


def generate(params: dict, api_key: str, do_scrape: bool, tavily_key: str = ""):
    if not api_key:
        st.error("⚠️ Ingresá tu API key en la barra lateral.")
        return

    scraped_ctx, sources = "", []

    if do_scrape:
        with st.spinner("🌐 Obteniendo datos (Sofascore · Transfermarkt · Wikipedia)…"):
            scraped_ctx, sources = scrape_context(params)

        # Tavily como capa adicional de stats (si hay key)
        if tavily_key:
            with st.spinner("🔍 Buscando stats adicionales (Tavily)…"):
                tav = _tavily_for_params(params, tavily_key)
                if tav:
                    scraped_ctx = scraped_ctx + "\n\n" + tav if scraped_ctx else tav
                    if "Tavily" not in sources:
                        sources.append("Tavily Stats")

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
                max_tokens=1000,
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
    st.markdown("### 🔑 Anthropic API Key")
    has_secret = bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
    if has_secret:
        st.success("✓ Configurada en Secrets")
        api_key_input = ""
    else:
        api_key_input = st.text_input(
            "Anthropic Key", type="password", placeholder="sk-ant-api03-…",
            label_visibility="collapsed",
            help="Ingresá tu API key de Anthropic"
        )
        if api_key_input:
            if api_key_input.startswith("sk-ant-"):
                st.success("✓ Key lista")
            else:
                st.error("⚠ Debe empezar con sk-ant-")
        st.markdown("[↗ Obtener key](https://console.anthropic.com/settings/keys)")

    api_key = get_api_key(api_key_input)

    st.divider()
    st.markdown("### 📊 Tavily Stats")
    st.caption("Búsqueda en sitios de estadísticas (fbref, transfermarkt, sofascore, etc.)")

    has_tavily_secret = bool(st.secrets.get("TAVILY_API_KEY", ""))
    if has_tavily_secret:
        st.success("✓ Configurada en Secrets")
        tavily_key_input = ""
    else:
        tavily_key_input = st.text_input(
            "Tavily Key", type="password", placeholder="tvly-…",
            label_visibility="collapsed",
            help="Opcional. Mejora la calidad de datos stats."
        )
        if tavily_key_input:
            st.success("✓ Tavily activo")
        st.markdown("[↗ Key gratuita (1000/mes)](https://app.tavily.com)")

    tavily_key = get_tavily_key(tavily_key_input)

    if tavily_key:
        st.caption("🔍 fbref · transfermarkt · sofascore\nflashscore · soccerway · whoscored\npromiedos · bdfa")

    st.divider()
    st.markdown("### 🌐 Scraping gratuito")
    do_scrape = st.toggle(
        "Activar scraping", value=True,
        help="Sofascore API + Wikipedia + Transfermarkt API. Sin costo extra.",
    )
    if do_scrape:
        st.caption("✅ Sofascore API\n✅ Transfermarkt API\n✅ Wikipedia")
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
                api_key, do_scrape, tavily_key,
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
                api_key, do_scrape, tavily_key,
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
                api_key, do_scrape, tavily_key,
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
            generate({"type": "libre", "prompt": libre_text.strip()}, api_key, do_scrape, tavily_key)

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
