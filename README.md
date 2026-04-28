# ◈ ORBITRA CORE

> **Deterministic web intelligence. No AI. No APIs. Pure algorithms.**

A fully self-hosted, async web crawler and lead intelligence engine built for discovering business contacts, researching markets, and mapping the web — without depending on OpenAI, Anthropic, or any external AI service.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Crawl Modes](#crawl-modes)
- [Concurrency Profiles](#concurrency-profiles)
- [Multilingual Query Expansion](#multilingual-query-expansion)
- [Scoring Algorithm](#scoring-algorithm)
- [Accuracy Goal](#accuracy-goal)
- [Language Settings](#language-settings)
- [Outputs](#outputs)
- [Dashboard](#dashboard)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [Translations / 多语言说明](#translations)

---

## What It Does

ORBITRA CORE crawls the web using deterministic, rule-based algorithms to:

- **Discover** relevant websites from multiple search engines (DuckDuckGo Lite, Yahoo, Brave, Ecosia) + CommonCrawl CDX
- **Extract** emails, phone numbers, WeChat IDs, LINE IDs, organisations, locations from page content using regex and proximity scoring
- **Score** every page 0–100 using a weighted breakdown of keyword frequency, semantic clusters, contact presence, content quality, multilingual signals, metadata, and link authority
- **Expand** queries into 15+ languages including Chinese, Japanese, Korean, German, Dutch, French, Spanish, Portuguese, Italian, Russian, Arabic, Thai, Malay, Vietnamese
- **Output** structured results as JSON, CSV, and a standalone HTML intelligence board

Zero external AI calls. Zero cloud dependencies. Runs entirely on your machine.

---

## Architecture

```
orbitra/
├── main.py                  Entry point — CLI menu, job runner
├── config.py                Concurrency profiles, score weights, semantic clusters
├── lang_expansions.py       Multilingual translation dictionaries (15+ languages)
├── prefs.py                 Local user preferences (~/.orbitra/prefs.json)
│
├── core/
│   ├── crawler.py           Async Playwright browser pool with stealth patches
│   ├── extractor.py         BeautifulSoup HTML parser, entity regex extraction
│   ├── scorer.py            Deterministic 0–100 scoring + multilingual query expansion
│   └── graph.py             BFS crawl graph, frontier management, pruning
│
├── modules/
│   ├── discovery.py         Multi-engine URL discovery + geographic fallback seeds
│   ├── website.py           Logo, colour palette, nav, social link detection
│   └── fingerprint.py       CMS/framework/CDN/analytics fingerprinting
│
├── db/
│   └── database.py          SQLite WAL — jobs, pages, graph edges, query expansions
│
├── ui/
│   └── tui.py               Rich-based async TUI — live feed, hotkeys, language chooser
│
└── web/
    ├── server.py             FastAPI + SSE dashboard backend
    └── static/
        └── dashboard.html   Standalone SaaS-style dashboard
```

### Data Flow

```
Query
  │
  ▼
expand_queries()          Multilingual expansion → up to 15 search strings
  │
  ▼
discover_urls()           DDG → Yahoo → Brave → Ecosia → CDX augment
  │                       + curated geo-aware fallback seeds
  ▼
CrawlGraph                BFS frontier, domain caps (50/domain), score-based pruning
  │
  ▼
Crawler.fetch()           Playwright + stealth + request interception + retry backoff
  │
  ▼
extract()                 BeautifulSoup: entities, headings, main text, schema.org, OG
  │
  ▼
score_page()              Weighted scoring breakdown → 0–100 integer
  │
  ▼
SQLite WAL                Upsert pages, edges, job state
  │
  ▼
_write_outputs()          results.json · leads.csv · graph.json · raw_pages.json · meta.json
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- macOS / Linux

### Install

```bash
git clone https://github.com/emmi-dev12/Orbitra.git
cd Orbitra
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Global Command

```bash
# Add a global orbitra command
mkdir -p ~/.local/bin
cat > ~/.local/bin/orbitra << 'EOF'
#!/bin/sh
exec /path/to/orbitra/.venv/bin/python /path/to/orbitra/main.py "$@"
EOF
chmod +x ~/.local/bin/orbitra
# Then add ~/.local/bin to your PATH in ~/.zshrc or ~/.bash_profile
```

### Run

```bash
orbitra                    # Interactive menu
orbitra --dashboard        # Launch web dashboard at http://localhost:7331
orbitra --verbose          # Enable debug logging
```

---

## Crawl Modes

| Mode | Purpose | Scoring Bias |
|------|---------|-------------|
| **Personal** | Analyze specific URLs you provide | Keyword match, content quality |
| **Research** | Map a topic landscape — discover the ecosystem | Semantic clusters, link authority |
| **Lead Gen** | Find business contacts, emails, WeChat | Contact presence (40% weight) |

---

## Concurrency Profiles

| Profile | Max Pages | Browsers | Delay | Use Case |
|---------|-----------|----------|-------|----------|
| **Light** | 10 | 2 | 1.5s | Polite crawl, single site |
| **Medium** | 30 | 8 | 0.5s | Standard research jobs |
| **Heavy** | 80 | 20 | 0.1s | Broad lead gen sweeps |

---

## Multilingual Query Expansion

ORBITRA detects the target region from your query and automatically expands into relevant languages. **No Chinese is added for European or American queries.**

### Region → Auto Language Mapping

| Region | Detected Keywords | Languages Added |
|--------|------------------|-----------------|
| SE Asia | thailand, bangkok, singapore, malaysia, vietnam… | Chinese, Thai, Malay, Vietnamese |
| China / HK | china, hong kong, beijing, shanghai… | Chinese Simplified + Traditional |
| Japan | japan, tokyo, osaka… | Japanese |
| Korea | korea, seoul… | Korean |
| Europe (DE/AT/CH) | germany, austria, switzerland | German |
| Europe (FR/BE/CH) | france, belgium | French |
| Europe (ES) | spain | Spanish |
| Europe (IT) | italy | Italian |
| Europe (NL/BE) | netherlands, belgium | Dutch |
| Europe (RU/UA) | russia, ukraine | Russian |
| Middle East | dubai, uae, qatar, saudi… | Arabic |
| Latin America | brazil, mexico, argentina… | Spanish, Portuguese |

### Supported Languages

| Code | Language | Native Name |
|------|---------|------------|
| `zh` | Chinese Simplified | 中文（简体） |
| `zh_tw` | Chinese Traditional | 中文（繁體） |
| `ja` | Japanese | 日本語 |
| `ko` | Korean | 한국어 |
| `de` | German | Deutsch |
| `nl` | Dutch | Nederlands |
| `fr` | French | Français |
| `es` | Spanish | Español |
| `pt` | Portuguese | Português |
| `it` | Italian | Italiano |
| `ru` | Russian | Русский |
| `ar` | Arabic | العربية |
| `th` | Thai | ภาษาไทย |
| `ms` | Malay / Indonesian | Bahasa Melayu |
| `vi` | Vietnamese | Tiếng Việt |

### Override Language Selection

From the main menu, choose **Language Settings** (option 5) to manually select languages. Your choice persists to `~/.orbitra/prefs.json`.

```
# Always use German + French regardless of query
Enter language codes: de,fr

# Auto-detect from query region (default)
Enter language codes: auto
```

---

## Scoring Algorithm

Every crawled page receives a score from **0 to 100**. The breakdown:

### Score Weights by Mode

| Component | Personal | Research | Lead Gen |
|-----------|----------|----------|----------|
| Keyword Frequency | 30 | 20 | 15 |
| Semantic Clusters | 15 | 25 | 10 |
| **Contact Presence** | 15 | 10 | **40** |
| Content Length | 15 | 8 | 5 |
| Multilingual Signal | 8 | 10 | 15 |
| Metadata Quality | 10 | 7 | 5 |
| Link Authority | 7 | 20 | 10 |

### Penalty System

Pages lose points for:

| Issue | Penalty |
|-------|---------|
| Thin content (< 50 words) | −20 |
| No headings | −5 |
| Keyword stuffing (> 5% word freq) | −15 |
| No metadata | −3 |

Penalty severity scales with the **Accuracy Goal** (see below).

### Semantic Clusters

ORBITRA matches pages against pre-built keyword clusters: `sports`, `travel`, `business`, `contact`, `education`. Pages that hit multiple clusters score higher. Cluster matching uses substring matching across the full page text + title.

### Entity Extraction

Extracted deterministically using regex:

| Entity | Method |
|--------|--------|
| Email | RFC 5321 compliant regex |
| Phone | Regional E.164 patterns (TH/CN/SG/HK/MY/VN/EU/US) |
| WeChat | 微信/wechat proximity + alphanumeric ID pattern |
| LINE | LINE ID proximity patterns |
| Organisations | Suffix-keyword matching (Ltd, Corp, 有限公司…) |
| Locations | 2000+ city/country names database |

---

## Accuracy Goal

Set before each job (0–100%). Controls how strictly results are filtered.

| Goal | Lead Min Score | Penalty Scale | Use Case |
|------|---------------|---------------|----------|
| 0% | 0 | 0.5× | Maximum recall — everything with a contact qualifies |
| 50% | 17 | 1.0× | Balanced (recommended default) |
| 75% | 26 | 1.25× | High confidence leads only |
| 100% | 35 | 1.5× | Only clearly relevant, high-content pages |

---

## Language Settings

Preferences persist to `~/.orbitra/prefs.json`:

```json
{
  "expansion_langs": ["zh", "de"],
  "accuracy_goal": 75,
  "default_mode": "leadgen",
  "default_profile": "medium"
}
```

To reset: delete `~/.orbitra/prefs.json` or set `expansion_langs` to `[]`.

---

## Outputs

Every job writes to `results/jobs/<job-id>/`:

| File | Contents |
|------|---------|
| `results.json` | All pages sorted by score, with full scoring breakdown |
| `leads.csv` | Pages with contact info above accuracy threshold |
| `graph.json` | Full crawl graph — nodes, edges, depths, scores |
| `raw_pages.json` | All pages including extracted text (5000 char limit) |
| `meta.json` | Job metadata, stats, elapsed time, expanded queries |

### Intelligence Board (`board.html`)

After a job, open the board in any browser — no server required:

- **Kanban** and **Table** views
- **Group by**: Sureness (Hot 🔥 / Warm ⚡ / Cold ❄), Category, Contact Quality
- **Filters**: Has Contact, SE Asia Only, Score ≥20
- **Search** across titles, URLs, emails
- **Score breakdown** modal per page
- Fully standalone — all data embedded as JS

---

## Dashboard

```bash
orbitra --dashboard
# Open http://localhost:7331
```

Features:
- Live job creation with query preview and chip editor
- Real-time Server-Sent Events feed
- Results table with score bars, sort, filter
- Page inspector panel
- Graph visualization
- Single-URL site analyzer
- Download CSV / JSON / graph

---

## CLI Reference

```bash
orbitra                    # Interactive menu
orbitra --dashboard        # Launch web dashboard
orbitra --verbose          # Enable debug logging
orbitra --port 8080        # Custom dashboard port
```

### TUI Hotkeys (during crawl)

| Key | Action |
|-----|--------|
| `E` | Toggle expanded / compact view |
| `Q` | Cancel job |

---

## Configuration

Edit `config.py`:

```python
PROFILES = {
    "light":  ConcurrencyProfile(max_pages=10,  max_browsers=2,  request_delay=1.5),
    "medium": ConcurrencyProfile(max_pages=30,  max_browsers=8,  request_delay=0.5),
    "heavy":  ConcurrencyProfile(max_pages=80,  max_browsers=20, request_delay=0.1),
}

MAX_DEPTH = 5                    # Max crawl depth from seed
MAX_PAGES_PER_DOMAIN = 50        # Hard cap per domain
MAX_SEEDS_FROM_DISCOVERY = 200   # Max seeds from search engines

BLOCKED_RESOURCE_TYPES = ["image", "font", "media", "stylesheet"]
```

---

## Translations

### 中文（简体）

ORBITRA CORE 是一个完全自托管的网络爬虫和商业情报引擎。无需 AI，无需外部 API，纯算法驱动。

**主要功能：**
- 多引擎 URL 发现（DuckDuckGo、雅虎、Brave、Ecosia + CommonCrawl）
- 从网页中提取邮箱、电话、微信 ID、组织、地点（正则表达式）
- 确定性评分算法（0–100 分），多维度加权
- 多语言查询扩展：支持中文、日语、韩语、德语、荷兰语、法语、西班牙语等 15 种语言
- **地区智能**：查询"东南亚篮球"自动生成中文变体；查询"瑞士篮球"则生成德语和法语变体，不添加中文
- 精度目标（0–100%）：控制线索质量门槛（得分要求与惩罚力度）
- 输出格式：JSON、CSV、HTML 智能看板（Kanban 式，无需服务器）

**快速开始：**
```bash
git clone https://github.com/emmi-dev12/Orbitra.git
cd Orbitra
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python main.py
```

**语言偏好**（持久化至 `~/.orbitra/prefs.json`）：
从主菜单选择「语言设置」，输入语言代码（如 `zh,de,fr`）或选择 `auto` 自动检测。

---

### 日本語

ORBITRA CORE は、完全自己ホスト型の Web クローラーおよびリードインテリジェンスエンジンです。AI 不使用・外部 API 不要・純粋なアルゴリズムで動作します。

**主な機能：**
- 複数の検索エンジン（DDG、Yahoo、Brave、Ecosia）と CommonCrawl による URL 発見
- メール・電話番号・WeChat ID・組織名・所在地を正規表現で抽出
- 0〜100 の決定論的スコアリング（キーワード頻度、セマンティッククラスター、コンタクト有無など 7 要素）
- クエリを 15 以上の言語に拡張（地域を自動検出）
- 精度目標（0〜100%）でリード品質を管理
- JSON・CSV・スタンドアロン HTML ボードとして出力

---

### Deutsch

ORBITRA CORE ist eine vollständig selbst gehostete Web-Crawling- und Business-Intelligence-Engine. Kein KI, keine externen APIs — deterministisch durch und durch.

**Kernfunktionen:**
- URL-Entdeckung über DuckDuckGo, Yahoo, Brave, Ecosia + CommonCrawl
- Regex-Extraktion von E-Mails, Telefonnummern, WeChat-IDs, Organisationen, Standorten
- Deterministisches Scoring-System (0–100 Punkte), gewichtet nach Crawl-Modus
- Mehrsprachige Abfrageerweiterung für 15+ Sprachen mit automatischer Regionserkennung
  - Schweizer Suchanfrage → Deutsch + Französisch (kein Chinesisch)
  - SE-Asien-Suchanfrage → Chinesisch + Thai + Malaiisch
- Genauigkeitsziel (0–100%) steuert Lead-Qualitätsschwelle und Strafgewichtung
- Export als JSON, CSV und interaktives HTML-Kanban-Board

---

### Français

ORBITRA CORE est un moteur de crawl web et d'intelligence commerciale auto-hébergé. Sans IA, sans API externe — des algorithmes déterministes uniquement.

**Fonctionnalités principales :**
- Découverte d'URL via DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Extraction regex d'e-mails, téléphones, WeChat, organisations, localisations
- Scoring déterministe 0–100, pondéré selon le mode de crawl
- Expansion de requêtes en 15+ langues avec détection automatique de la région
  - Requête européenne → Allemand, Français, Espagnol (pas de Chinois)
  - Requête Asie du Sud-Est → Chinois, Thaï, Malais
- Objectif de précision (0–100%) pour le seuil de qualité des leads
- Export JSON, CSV, tableau HTML Kanban autonome

---

### Nederlands

ORBITRA CORE is een volledig zelf-gehoste webcrawler en business intelligence-engine. Geen AI, geen externe API's — puur deterministische algoritmen.

**Kernfuncties:**
- URL-ontdekking via DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Regex-extractie van e-mails, telefoonnummers, WeChat-ID's, organisaties en locaties
- Deterministisch scoresysteem (0–100), gewogen per crawlmodus
- Meertalige queryuitbreiding voor 15+ talen met automatische regiodetectie
- Nauwkeurigheidsdoel (0–100%) voor kwaliteitsdrempel leads
- Export als JSON, CSV en interactief HTML Kanban-board

---

### Español

ORBITRA CORE es un motor de rastreo web e inteligencia de negocios completamente autoalojado. Sin IA, sin APIs externas — solo algoritmos deterministas.

**Características:**
- Descubrimiento de URLs vía DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Extracción regex de correos, teléfonos, WeChat, organizaciones y ubicaciones
- Puntuación determinista 0–100, ponderada por modo de rastreo
- Expansión de consultas en 15+ idiomas con detección automática de región
- Objetivo de precisión (0–100%) para umbral de calidad de leads
- Exportación en JSON, CSV y tablero HTML Kanban independiente

---

### Português

ORBITRA CORE é um motor de rastreamento web e inteligência de negócios totalmente auto-hospedado. Sem IA, sem APIs externas — apenas algoritmos determinísticos.

**Funcionalidades:**
- Descoberta de URLs via DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Extração regex de e-mails, telefones, WeChat, organizações e localizações
- Sistema de pontuação determinístico (0–100), ponderado por modo
- Expansão de consultas em 15+ idiomas com detecção automática de região
- Meta de precisão (0–100%) para limiar de qualidade de leads
- Exportação em JSON, CSV e painel HTML Kanban independente

---

### Italiano

ORBITRA CORE è un motore di crawling web e intelligence aziendale completamente self-hosted. Nessuna IA, nessuna API esterna.

**Funzionalità principali:**
- Scoperta URL tramite DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Estrazione regex di email, telefoni, WeChat, organizzazioni e luoghi
- Scoring deterministico 0–100, pesato per modalità di crawl
- Espansione query in 15+ lingue con rilevamento automatico della regione
- Obiettivo di precisione (0–100%) per soglia qualità lead
- Export JSON, CSV, board HTML Kanban standalone

---

### Русский

ORBITRA CORE — полностью самостоятельный веб-краулер и движок бизнес-разведки. Без ИИ, без внешних API — только детерминированные алгоритмы.

**Ключевые возможности:**
- Обнаружение URL через DDG, Yahoo, Brave, Ecosia + CommonCrawl
- Regex-извлечение email, телефонов, WeChat, организаций и местоположений
- Детерминированная оценка 0–100 баллов по 7 параметрам
- Расширение запросов на 15+ языках с автоматическим определением региона
- Цель точности (0–100%) для порога качества лидов
- Экспорт в JSON, CSV и HTML Kanban-доску

---

### العربية

ORBITRA CORE هو محرك زحف ويب واستخبارات أعمال مستضاف ذاتيًا بالكامل. بدون ذكاء اصطناعي، بدون واجهات برمجية خارجية.

**الميزات الرئيسية:**
- اكتشاف عناوين URL عبر DDG وYahoo وBrave وEcosia + CommonCrawl
- استخراج البريد الإلكتروني والهاتف وWeChat والمنظمات والمواقع بالتعبيرات النمطية
- تسجيل حتمي 0–100 نقطة موزون حسب وضع الزحف
- توسيع الاستعلامات إلى 15+ لغة مع الكشف التلقائي عن المنطقة
- هدف الدقة (0–100%) للتحكم في جودة العملاء المحتملين
- التصدير إلى JSON وCSV ولوحة HTML Kanban مستقلة

---

### ภาษาไทย

ORBITRA CORE คือระบบ Web Crawler และ Business Intelligence ที่โฮสต์เองได้ ไม่มี AI ไม่มี API ภายนอก

**คุณสมบัติหลัก:**
- ค้นหา URL จาก DDG, Yahoo, Brave, Ecosia + CommonCrawl
- ดึงข้อมูลอีเมล เบอร์โทร WeChat องค์กร และสถานที่ด้วย Regex
- ให้คะแนนแน่นอน 0–100 คะแนน ตามน้ำหนักแต่ละโหมด
- ขยายคำค้นหาเป็น 15+ ภาษา พร้อมตรวจจับภูมิภาคอัตโนมัติ
- เป้าหมายความแม่นยำ (0–100%) สำหรับควบคุมคุณภาพ Lead
- ส่งออกเป็น JSON, CSV และ HTML Kanban Dashboard

---

## License

MIT — use it however you like.

---

*Built with: Python · Playwright · BeautifulSoup · FastAPI · SQLite · Rich*  
*No AI was used in generating these results. No cloud. No subscriptions. Just code.*
