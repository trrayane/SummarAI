"""
tools/web_scraper.py
Extraction du contenu textuel d'une page web à partir d'une URL.
"""

import httpx
from bs4 import BeautifulSoup

# Balises à supprimer avant extraction du texte
_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside",
               "noscript", "iframe", "form", "button", "svg"]

# Limite de caractères envoyés au modèle (~4000 tokens)
MAX_CHARS = 12_000


async def extract_text_from_url(url: str) -> str:
    """
    Récupère et nettoie le contenu textuel d'une page web.

    Args:
        url: URL de la page à scraper (doit commencer par http:// ou https://).

    Returns:
        Texte brut nettoyé, limité à MAX_CHARS caractères.

    Raises:
        ValueError: URL invalide ou inaccessible.
        RuntimeError: Erreur réseau ou de parsing.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL invalide : {url!r}. Elle doit commencer par http:// ou https://")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SummarAI/1.0)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"La page a retourné une erreur HTTP {exc.response.status_code} : {url}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Impossible d'accéder à l'URL : {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")

    # Suppression des éléments parasites
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # Priorité au contenu principal (article, main, etc.)
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id="content")
        or soup.find(class_="content")
        or soup.body
    )

    raw = (main or soup).get_text(separator="\n", strip=True)

    # Nettoyage des lignes vides répétées
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    text = "\n".join(lines)

    return text[:MAX_CHARS]