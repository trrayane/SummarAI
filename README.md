<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini"/>
  <img src="https://img.shields.io/badge/LangChain-0.2-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangChain"/>
  <img src="https://img.shields.io/badge/NLTK-3.8-154F5B?style=for-the-badge" alt="NLTK"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">SummarAI</h1>
<h3 align="center">Assistant de résumé intelligent pour texte, fichiers et pages web</h3>

---

## Table des matières

- [Présentation](#présentation)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Structure du projet](#structure-du-projet)
- [Installation](#installation)
- [Configuration](#configuration)
- [Exécution](#exécution)
- [API](#api)
- [Bonnes pratiques](#bonnes-pratiques)
- [Pour aller plus loin](#pour-aller-plus-loin)
- [Licence](#licence)

---

## Présentation

SummarAI est une application de résumé de contenu qui transforme automatiquement du texte brut, des fichiers et des pages web en synthèses lisibles.

Le projet combine :

- un backend **Python / FastAPI** pour servir l’API et l’interface statique
- un moteur de génération basé sur **Google Gemini 2.5 Flash**
- un prétraitement linguistique avec **NLTK**
- une extraction de contenu depuis **PDF, DOCX, TXT** et **URLs web**
- un mode **Q&A** pour interroger le document après résumé

SummarAI est conçu pour être déployé localement en développement et offre une base claire pour ajouter de l’authentification, du stockage persistant ou un packaging Docker.

---

## Fonctionnalités

- Résumé de contenu à partir du texte saisi
- Résumé de contenu à partir de fichiers PDF, DOCX et TXT
- Résumé de contenu à partir d’une URL web
- Streaming du résumé vers le front-end via SSE pour un rendu progressif
- Q&A basé sur le document résumé
- Historique de sessions et des résumés
- Prétraitement NLP afin d’améliorer la qualité des prompts
- Frontend statique servi par le backend

---


## Architecture

```mermaid
%% Diagramme d'architecture SummarAI
graph TD
  A[Utilisateur] -->|Texte/Fichier/URL| B[Frontend statique]
  B -->|Requête API| C[FastAPI Backend]
  C --> D[Prétraitement NLP (NLTK)]
  C --> E[Extraction PDF/DOCX/TXT/URL]
  C --> F[Gemini 2.5 Flash (API)]
  C --> G[Historique MySQL]
  C --> H[Session Store]
  F -->|Résumé/Q&A| B
  G -->|Historique| B
```

Les composants principaux sont :

- `backend/main.py` : point d’entrée de l’application, configuration CORS, lifecyle FastAPI et montage des fichiers statiques
- `backend/api/routes.py` : définition des endpoints REST (`/api/v1/summarize`, `/api/v1/ask`, `/api/v1/health`)
- `backend/agents/summarizer_agent.py` : orchestration du résumé et de la logique Q&A
- `backend/services/gemini_service.py` : wrapper d’appel vers Gemini et LangChain
- `backend/services/history_service.py` : stockage et récupération de l’historique des résumés
- `backend/preprocessing/nltk_processor.py` : nettoyage du texte et génération de données utiles pour les prompts
- `backend/tools/file_parser.py` : extraction de texte depuis PDF, DOCX et TXT
- `backend/tools/web_scraper.py` : récupération et nettoyage de contenu HTML depuis une URL
- `backend/memory/session_store.py` : gestion de la session et du document courant pour le mode Q&A
- `backend/static/index.html` : interface utilisateur de l’application

---

## Structure du projet

Voici l’arborescence complète avec une description de chaque élément :

### Racine

- `README.md` : documentation du projet
- `.env` : fichier de configuration des variables d’environnement (non versionné)
- `.gitignore` : ignore les fichiers temporaires et l’environnement virtuel
- `backend/` : dossier principal de l’application

### Dossier `backend/`

- `main.py` : lancement du serveur FastAPI et montage du frontend
- `requirements.txt` : dépendances Python listées pour `pip install`
- `venv/` : environnement virtuel local (à ignorer dans le dépôt)

#### `backend/agents/`

- `summarizer_agent.py` : logique métier de résumé et Q&A

#### `backend/api/`

- `routes.py` : routes FastAPI exposant l’API

#### `backend/config/`

- `settings.py` : gestion des paramètres via `pydantic-settings`

#### `backend/memory/`

- `session_store.py` : stockage temporaire de session et des documents résumés

#### `backend/preprocessing/`

- `nltk_processor.py` : prétraitement du texte, tokenisation et nettoyage

#### `backend/prompts/`

- `style_prompts.py` : prompts définis pour les différents styles de résumé

#### `backend/services/`

- `gemini_service.py` : intégration avec le modèle Gemini
- `history_service.py` : historique et cache des résumés

#### `backend/tools/`

- `file_parser.py` : extraction de texte à partir de fichiers PDF, DOCX et TXT
- `web_scraper.py` : extraction de texte à partir de pages web

#### `backend/static/`

- `index.html` : interface utilisateur web statique

---


## Prérequis

- Python 3.10+
- pip
- (Optionnel) MySQL pour l’historique

## Installation

1. Placez-vous dans le dossier du projet :

```powershell
cd C:\Users\HP\Desktop\SummarAI
```

2. Créez et activez un environnement virtuel :

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

3. Installez les dépendances :

```powershell
pip install -r backend\requirements.txt
```

---

## Configuration

Créez un fichier `.env` dans le dossier `backend/` contenant les variables suivantes :

```env
GEMINI_API_KEY=ton_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.3
GEMINI_MAX_TOKENS=2048
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=rayane
MYSQL_DATABASE=ai_summarizer
HOST=0.0.0.0
PORT=8000
DEBUG=True
ALLOWED_ORIGINS=["*"]
```

- `GEMINI_API_KEY` : clé API Gemini
- `MYSQL_*` : configuration MySQL pour l’historique
- `HOST`, `PORT`, `DEBUG` : configuration du serveur
- `ALLOWED_ORIGINS` : origines autorisées pour CORS

> Si MySQL est indisponible, le backend continuera de fonctionner sans historique.

---


## Exemples d'utilisation API

### Résumer un texte (curl)

```bash
curl -X POST "http://localhost:8000/api/v1/summarize" \
  -H "Content-Type: application/json" \
  -d '{"source": "texte", "content": "Votre texte à résumer ici."}'
```

### Résumer un fichier (Python)

```python
import requests
files = {'file': open('monfichier.pdf', 'rb')}
r = requests.post('http://localhost:8000/api/v1/summarize', files=files)
print(r.json())
```

### Q&A sur un résumé

```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "question": "Quelle est la thèse principale ?"}'
```

## Liens utiles

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Gemini API](https://ai.google.dev/gemini-api/docs)
- [LangChain](https://python.langchain.com/)
- [NLTK](https://www.nltk.org/)


Lancez l’application depuis `backend/` :

```powershell
python main.py
```

Ensuite, ouvrez l’application :

- Interface utilisateur : `http://localhost:8000`
- Swagger UI : `http://localhost:8000/docs`

---

## API

### POST `/api/v1/summarize`

Cet endpoint reçoit un texte, un fichier ou une URL et renvoie un résumé.

- Source : texte libre, fichier PDF/DOCX/TXT, URL
- Résultat : résumé textuel généré par Gemini
- Streaming : le backend peut renvoyer les tokens au fur et à mesure via SSE

### POST `/api/v1/ask`

Cet endpoint reçoit une question et une session, puis renvoie une réponse contextualisée sur le document résumé.

- Utilise la session pour retrouver le document stocké
- Interroge le modèle avec le contexte du texte source

### GET `/api/v1/health`

Endpoint de contrôle pour vérifier si le service est actif.

---

## Bonnes pratiques

- Ne commitez jamais votre clé Gemini.
- En production, utilisez `DEBUG=False`.
- Restreignez `ALLOWED_ORIGINS` à vos domaines applicatifs.
- Limitez la taille des documents pour rester dans les quotas Gemini.
- Ajoutez une gestion d’erreurs réseau / timeout pour l’API Gemini.

---

## Pour aller plus loin

Idées d’amélioration :

- Ajout de l’authentification et des utilisateurs
- Stockage persistant avec base de données et historique utilisateur
- Interface de gestion des résumés
- Déploiement Docker / Kubernetes
- Extension du parsing web pour gérer plus de sites
- Ajout d’un vrai frontend React ou Vue

---

## Licence

Ce projet est distribué sous licence **MIT**.
