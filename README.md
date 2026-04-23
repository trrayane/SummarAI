<div align="center">

# 🧠 SummarAI

**Transform any content into intelligent summaries — powered by Google Gemini**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![MySQL](https://img.shields.io/badge/MySQL-8.3-4479A1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![NLTK](https://img.shields.io/badge/NLTK-3.8-154F5B?style=flat-square)](https://nltk.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[Demo](#-demo) · [Features](#-features) · [Installation](#-installation) · [API Docs](#-api-reference) · [Architecture](#-architecture)

</div>

---

## 📌 Overview

SummarAI is a production-ready web application that summarizes any content — raw text, PDF/DOCX/TXT files, or web pages — using Google Gemini 2.5 Flash with real-time streaming. It also enables Q&A on the original document, generates automatic titles, and maintains a persistent history.

**Key highlights:**
- ⚡ **Real-time streaming** — results appear token by token via Server-Sent Events
- 🗂️ **Multi-source input** — paste text, upload files, or provide a URL
- 🤖 **NLP pre-processing** — NLTK extracts key sentences before sending to Gemini
- 🗃️ **Smart caching** — identical inputs return instantly (95%+ time saved)
- ❓ **Document Q&A** — ask questions about any summarized document

---

## ✨ Features

| Feature | Details |
|---|---|
| **Text summarization** | Up to 100,000 characters |
| **File summarization** | PDF, DOCX, TXT — up to 10 MB |
| **Web page summarization** | Scrapes and cleans any URL |
| **Summary styles** | Concise · Detailed · Bullet points |
| **Document Q&A** | Session-based, answers grounded in source text |
| **Auto title generation** | 3–6 word title created by Gemini |
| **Persistent history** | All summaries stored in MySQL |
| **In-memory cache** | SHA-256 keyed, 1-hour TTL |

---

## 🚀 Demo

> Coming soon — screenshots and live demo link

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Frontend (HTML/JS/CSS)          │  ← Vanilla JS + SSE streaming
└────────────────────┬────────────────────┘
                     │ HTTP / SSE
                     ▼
┌─────────────────────────────────────────┐
│           FastAPI Backend               │  ← Routing, validation, CORS
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│          SummarizerAgent                │  ← Pipeline orchestration
│                                         │
│  1. Parse (PDF / DOCX / URL / text)     │
│  2. Detect language                     │
│  3. NLP pre-processing (NLTK)           │
│  4. Cache lookup                        │
│  5. Stream summary via Gemini           │
│  6. Generate title                      │
│  7. Save to MySQL + session store       │
└──────┬──────────────────────────┬───────┘
       │                          │
       ▼                          ▼
┌─────────────┐          ┌────────────────┐
│ Google      │          │ MySQL Database │
│ Gemini API  │          │ (history)      │
└─────────────┘          └────────────────┘
```

### Project structure

```
backend/
├── main.py                   # FastAPI entry point
├── requirements.txt
├── config/
│   └── settings.py           # Environment config
├── api/
│   └── routes.py             # POST /summarize, POST /ask
├── agents/
│   └── summarizer_agent.py   # Main pipeline orchestrator
├── services/
│   ├── gemini_service.py     # Gemini API + streaming + cache
│   └── history_service.py    # MySQL CRUD
├── tools/
│   ├── file_parser.py        # PDF / DOCX / TXT extraction
│   ├── language_detector.py  # langdetect + heuristic fallback
│   └── web_scraper.py        # httpx + BeautifulSoup
├── preprocessing/
│   └── nltk_processor.py     # Tokenization, TF-IDF scoring
├── memory/
│   └── session_store.py      # In-memory Q&A sessions (1h TTL)
├── prompts/
│   └── style_prompts.py      # Gemini prompt templates
└── static/
    └── index.html            # Frontend
```

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- A [Google Gemini API key](https://ai.google.dev/)

### 1. Clone the repository

```bash
git clone https://github.com/trrayane/SummarAI.git
cd summarai/backend
```

### 2. Create a virtual environment

```bash
# macOS / Linux
python -m venv venv && source venv/bin/activate

# Windows
python -m venv venv && .\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in `backend/`:

```env
# Google Gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=2048

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ai_summarizer

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=True
ALLOWED_ORIGINS=["*"]
```

### 5. Set up the database

```sql
CREATE DATABASE ai_summarizer;
USE ai_summarizer;

CREATE TABLE summaries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    text_hash VARCHAR(255) UNIQUE,
    original_text LONGTEXT,
    summary LONGTEXT,
    style VARCHAR(50),
    word_count INT,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    summary_id INT,
    question TEXT,
    answer LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (summary_id) REFERENCES summaries(id) ON DELETE CASCADE
);
```

### 6. Start the server

```bash
python main.py
```

| URL | Description |
|---|---|
| http://localhost:8000 | Web interface |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |

---

## 🔌 API Reference

### `POST /api/v1/summarize`

Summarize text, a file, or a URL. Returns a **streaming SSE** response.

**Form parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `text` | string | — | Raw text (max 100,000 chars) |
| `file` | file | — | PDF, DOCX, or TXT (max 10 MB) |
| `url` | string | — | Web page URL to scrape |
| `style` | string | — | `concis` (default) · `détaillé` · `bullet` |

**SSE stream format:**

```
data: __SESSION__<uuid>__
data: Summary token 1...
data: Summary token 2...
data: __TITLE__Generated Title__
data: [DONE]
```

**Examples:**

```bash
# Summarize raw text
curl -X POST http://localhost:8000/api/v1/summarize \
  -F "text=Your long document here..." \
  -F "style=concis"

# Summarize a PDF
curl -X POST http://localhost:8000/api/v1/summarize \
  -F "file=@/path/to/document.pdf" \
  -F "style=bullet"

# Summarize a web page
curl -X POST http://localhost:8000/api/v1/summarize \
  -F "url=https://example.com/article" \
  -F "style=détaillé"
```

---

### `POST /api/v1/ask`

Ask a question about a summarized document. Returns a **streaming SSE** response.

**Form parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | ✅ | Session ID from the summarize response |
| `question` | string | ✅ | Your question about the document |

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -F "session_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "question=What is the main topic?"
```

---

## ⚙️ How It Works

```
Input → Parse → Detect Language → NLP (NLTK) → Cache? → Gemini → Title → Save → Stream
```

1. **Parse** — Extract text from PDF/DOCX/TXT/URL
2. **Language detection** — English required for Q&A (langdetect + heuristic fallback)
3. **NLP pre-processing** — Tokenize, remove stopwords, score sentences by TF-IDF, extract top 30%
4. **Cache lookup** — SHA-256 hash of `style + text`; cache hit returns in ~0.1s
5. **Gemini streaming** — Tokens streamed to the client in real time
6. **Title generation** — Separate Gemini call for a 3–6 word title
7. **Persistence** — Summary saved to MySQL; session stored in memory for 1h Q&A

### Performance

| Operation | Time |
|---|---|
| PDF parsing | ~0.5s |
| Language detection | ~0.1s |
| NLP pre-processing | ~0.3s |
| Gemini streaming | 2–4s |
| Cache hit | ~0.1s ⚡ |
| **Total (cold)** | **3–5s** |
| **Total (cache)** | **~0.1s** |

---

## 🔒 Security

- Input validation: file size ≤ 10 MB, text ≤ 100,000 chars, extension whitelist
- Parameterized SQL queries (no raw interpolation)
- API key stored in `.env`, never exposed to the frontend
- Sessions are isolated per user and expire after 1 hour

---


## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS, EventSource API |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| AI | Google Gemini 2.5 Flash |
| NLP | NLTK (tokenization, TF-IDF) |
| File parsing | PyPDF2, python-docx |
| Web scraping | httpx, BeautifulSoup4 |
| Database | MySQL 8.3 |
| Language detection | langdetect |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

