from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from shared.config import CHROMA_PATH, EMBEDDING_MODEL, LLM_BASE_URL, OPENAI_API_KEY, SEED_DATA_DIR

COLLECTION_NAME = "hr_handbook"
_indexed = False


@dataclass
class SearchResult:
    content: str
    source: str
    score: float


def _chunk_markdown(text: str, source: str, chunk_size: int = 500) -> list[dict]:
    sections = re.split(r"\n(?=#{1,3}\s)", text)
    chunks: list[dict] = []

    # Derive location and category metadata from filename
    src_lower = source.lower()
    if "india" in src_lower:
        location_tag = "india"
    elif "usa" in src_lower:
        location_tag = "usa"
    elif "finland" in src_lower or "nordic" in src_lower:
        location_tag = "finland"
    else:
        location_tag = "global"

    if "benefit" in src_lower:
        category_tag = "benefits"
    elif "it-setup" in src_lower or "it_setup" in src_lower:
        category_tag = "it"
    elif "handbook" in src_lower:
        category_tag = "handbook"
    elif "compliance" in src_lower or "checklist" in src_lower:
        category_tag = "compliance"
    else:
        category_tag = "general"

    for section in sections:
        section = section.strip()
        if not section:
            continue
        for i in range(0, len(section), chunk_size):
            chunk = section[i : i + chunk_size].strip()
            if chunk:
                chunks.append({
                    "content": chunk,
                    "source": source,
                    "location": location_tag,
                    "category": category_tag,
                })
    return chunks


def _embedding_function():
    # Groq does NOT provide an embedding endpoint (only chat completions).
    # If using Groq (LLM_BASE_URL contains groq), or if no OpenAI key, use Chroma's built-in DefaultEmbeddingFunction.
    if OPENAI_API_KEY and not (LLM_BASE_URL and "groq.com" in LLM_BASE_URL):
        kwargs: dict[str, Any] = {
            "api_key": OPENAI_API_KEY,
            "model_name": EMBEDDING_MODEL,
        }
        if LLM_BASE_URL:
            kwargs["api_base"] = LLM_BASE_URL
        return embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    return embedding_functions.DefaultEmbeddingFunction()


def _get_client():
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def _get_collection():
    client = _get_client()
    ef = _embedding_function()
    try:
        return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    except ValueError:
        # Collection was indexed with a different embedding function (e.g. before API key was set).
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        global _indexed
        _indexed = False
        return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


def ensure_index() -> None:
    global _indexed
    if _indexed:
        return

    collection = _get_collection()
    if collection.count() > 0:
        _indexed = True
        return

    all_chunks: list[dict] = []
    for path in sorted(SEED_DATA_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        all_chunks.extend(_chunk_markdown(text, path.name))

    if not all_chunks:
        _indexed = True
        return

    collection.add(
        ids=[f"chunk-{i}" for i in range(len(all_chunks))],
        documents=[c["content"] for c in all_chunks],
        metadatas=[{"source": c["source"], "location": c["location"], "category": c["category"]} for c in all_chunks],
    )
    _indexed = True


def search_handbook(query: str, top_k: int = 3) -> list[SearchResult]:
    try:
        ensure_index()
        collection = _get_collection()
        results = collection.query(query_texts=[query], n_results=top_k)

        search_results: list[SearchResult] = []
        if not results["documents"] or not results["documents"][0]:
            return search_results

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            search_results.append(
                SearchResult(
                    content=doc,
                    source=meta.get("source", "unknown"),
                    score=1.0 - dist if dist is not None else 0.0,
                )
            )
        return search_results
    except Exception as e:
        # Fallback to direct keyword/text search over seed files if vector store hangs or fails
        return _fallback_keyword_search(query, top_k)


def _fallback_keyword_search(query: str, top_k: int = 3) -> list[SearchResult]:
    terms = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    all_chunks: list[dict] = []
    for path in sorted(SEED_DATA_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        all_chunks.extend(_chunk_markdown(text, path.name))

    scored = []
    for c in all_chunks:
        content_lower = c["content"].lower()
        score = sum(1 for t in terms if t in content_lower)
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        SearchResult(content=c["content"], source=c["source"], score=float(score))
        for score, c in scored[:top_k]
    ]

def format_search_results(results: list[SearchResult]) -> str:
    if not results:
        return "No relevant handbook sections found."

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] Source: {r.source}\n{r.content}")
    return "\n\n".join(parts)


def search_handbook_with_location(query: str, location: str | None = None, top_k: int = 4) -> list[SearchResult]:
    """Search handbook with location-aware filtering using ChromaDB native metadata.

    Applies a metadata ``where`` filter so only chunks tagged for the requested
    location (or 'global') are returned, eliminating cross-region contamination.
    Falls back to query enrichment when native filtering is unavailable.
    """
    location_map = {
        "india": "india",
        "usa": "usa",
        "united states": "usa",
        "us": "usa",
        "finland": "finland",
        "sweden": "finland",
        "germany": "global",
        "europe": "global",
    }
    loc_key = location_map.get(location.lower(), "global") if location else None

    # Also enrich the query text for better semantic retrieval
    query_enrichment_map = {
        "india": "India",
        "usa": "United States USA America",
        "finland": "Finland Helsinki",
    }
    enriched_query = query
    if loc_key and loc_key in query_enrichment_map:
        enriched_query = f"{query} {query_enrichment_map[loc_key]}"

    try:
        ensure_index()
        collection = _get_collection()
        n = min(top_k, collection.count() or top_k)

        # Attempt native metadata filter to avoid cross-region results
        where_filter: dict | None = None
        if loc_key and loc_key != "global":
            where_filter = {"$or": [{"location": loc_key}, {"location": "global"}]}

        try:
            if where_filter:
                results = collection.query(
                    query_texts=[enriched_query],
                    n_results=n,
                    where=where_filter,
                )
            else:
                results = collection.query(query_texts=[enriched_query], n_results=n)
        except Exception:
            # Metadata filter not supported (e.g. older Chroma or old index without location tag)
            # fall back to unfiltered query
            results = collection.query(query_texts=[enriched_query], n_results=n)

        search_results: list[SearchResult] = []
        if not results["documents"] or not results["documents"][0]:
            return search_results

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            search_results.append(
                SearchResult(
                    content=doc,
                    source=meta.get("source", "unknown"),
                    score=1.0 - dist if dist is not None else 0.0,
                )
            )
        return search_results
    except Exception:
        return _fallback_keyword_search(enriched_query, top_k)


def reindex_all() -> None:
    """Force a full reindex of all seed documents. Call when new documents are added."""
    global _indexed
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _indexed = False
    ensure_index()
