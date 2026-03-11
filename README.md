# ⚽ Ficha Deportiva IA

Generador de contenido periodístico deportivo con IA + scraping gratuito.

**Stack:** Streamlit · Claude API (Anthropic) · Sofascore · Wikipedia · DuckDuckGo

---

## 🚀 Deploy en Streamlit Community Cloud (gratis)

### 1. Subir a GitHub

```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/ficha-deportiva.git
git push -u origin main
```

### 2. Conectar en Streamlit Cloud

1. Entrá a [share.streamlit.io](https://share.streamlit.io)
2. **New app** → seleccioná tu repo → archivo: `ficha_deportiva.py`
3. Antes de deployar, abrí **Advanced settings → Secrets** y pegá:

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-TU-KEY-AQUI"
```

4. Click **Deploy** → en ~2 minutos tenés el link público ✅

---

## 💻 Correr localmente

```bash
pip install -r requirements.txt

# Crear el archivo de secrets (solo para uso local)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar secrets.toml y pegar tu API key real

streamlit run ficha_deportiva.py
```

---

## 🌐 Fuentes de datos (scraping gratuito)

| Fuente | Datos |
|--------|-------|
| **Sofascore API pública** | Stats de jugadores, resultados, plantillas |
| **Wikipedia REST API** | Perfiles, historia, datos biográficos |
| **DuckDuckGo HTML** | Noticias recientes, resultados, contexto |

Sin costo extra — reemplaza el web search pago de Anthropic.

---

## 🔑 API Key de Anthropic

Obtené la tuya gratis en [console.anthropic.com](https://console.anthropic.com/settings/keys).
