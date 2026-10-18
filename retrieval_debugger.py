"""DataLeak Retrieval Strategy Analyzer.

A Retrieval-Augmented Generation (RAG) pipeline over the Saudi Personal Data
Protection Law (PDPL) and the Personal Data Breach Incidents Procedural Guide
(PDBIG). Citations in the answers use these two abbreviations.

Pipeline:
    PDF extraction -> chunking -> embeddings (cached)
    -> Semantic Search (top 10) + BM25 (top 10)
    -> Cross-Encoder reranking (top 5)
    -> grounded answer generation with an LLM

Usage:
    python retrieval_debugger.py                 # interactive chat
    python retrieval_debugger.py -q "question"   # single query
    python -m streamlit run app.py               # web interface
"""

import argparse
import hashlib
import os
import re
import sys

import numpy as np
import pymupdf
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

load_dotenv()  # picks up OPENROUTER_API_KEY from a local .env file, if present

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "liquid/lfm-2.5-embedding-350m:free"
GENERATION_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EMBEDDING_CACHE = os.path.join(DATA_DIR, "embeddings_cache.npz")
DOCUMENTS = {
    "PersonalDataProtectionLaw": os.path.join(DATA_DIR, "raw", "PersonalDataProtectionLaw.pdf"),
    "PersonalDataBreachIncidents": os.path.join(DATA_DIR, "raw", "PersonalDataBreachIncidents.pdf"),
}
SOURCE_LABELS = {
    "PersonalDataProtectionLaw": "PDPL",
    "PersonalDataBreachIncidents": "PDBIG",
}
SOURCE_NAMES = {
    "PDPL": "Personal Data Protection Law",
    "PDBIG": "Personal Data Breach Incidents Procedural Guide",
}
ARTICLE_PATTERN = re.compile(r"\bArticle\s+(\d+)", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\w+")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MIN_CHUNK_CHARS = 50
SEMANTIC_TOP_K = 10
BM25_TOP_K = 10
RERANK_TOP_K = 5

PROMPT_TEMPLATE = """You are a retrieval-based question answering assistant.

Answer the user's question using ONLY the evidence provided below.

Rules:
- Do not use outside knowledge.
- Do not invent information.
- If the evidence is insufficient, clearly say that the provided documents do not contain enough information.
- Give a concise and direct answer.
- Cite every claim with the citation tag shown in brackets at the start of the evidence block it comes from,
  e.g. [PDPL · Article 6 · p. 4]. Place the citation at the end of the sentence it supports.
- Only use citation tags that appear in the evidence below.
- Source abbreviations: PDPL = Personal Data Protection Law; PDBIG = Personal Data Breach Incidents Procedural Guide.

Question:
{query}

Retrieved Evidence:
{context}
"""

SEPARATOR = "=" * 60


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------

def read_pdf(path):
    """Return a list of {page, text} dicts for every non-empty page."""
    pages = []
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                pages.append({"page": page_number, "text": text})
    return pages


def clean_text(text):
    """Strip classification banners, bare page numbers and extra whitespace."""
    text = re.sub(r"Document Classification:\s*Public", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*Public\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*!\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def make_citation(source, page, articles):
    """Human-readable citation tag, e.g. 'PDPL · Article 6 · p. 4'."""
    parts = [SOURCE_LABELS.get(source, source)]
    if articles:
        shown = ", ".join(str(a) for a in articles[:3])
        parts.append(f"Article {shown}" if len(articles) == 1 else f"Articles {shown}")
    parts.append(f"p. {page}")
    return " · ".join(parts)


def create_chunks(pages, source, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP, start_id=1):
    """Split cleaned page text into overlapping character chunks."""
    chunks = []
    chunk_id = start_id

    for page_data in pages:
        text = clean_text(page_data["text"])
        if len(text) < MIN_CHUNK_CHARS:
            continue

        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()

            if len(chunk_text) >= MIN_CHUNK_CHARS:
                articles = sorted({int(a) for a in ARTICLE_PATTERN.findall(chunk_text)})
                chunks.append({
                    "chunk_id": chunk_id,
                    "source": source,
                    "page": page_data["page"],
                    "articles": articles,
                    "citation": make_citation(source, page_data["page"], articles),
                    "text": chunk_text,
                })
                chunk_id += 1

            if end >= len(text):
                break
            start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def chunks_hash(chunks):
    """Fingerprint of chunk contents + embedding model, used to validate the cache."""
    content = EMBEDDING_MODEL
    for chunk in chunks:
        content += f"{chunk['chunk_id']}{chunk['source']}{chunk['page']}{chunk['text']}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_embeddings(client, chunks, batch_size=10):
    embeddings = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        end = min(start + batch_size, len(chunks))
        print(f"Creating embeddings {start + 1}-{end} of {len(chunks)}...")

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[chunk["text"] for chunk in batch],
        )
        embeddings.extend(item.embedding for item in response.data)

    return np.array(embeddings)


def load_or_create_embeddings(client, chunks):
    """Return cached embeddings when they match the current chunks, else rebuild."""
    current_hash = chunks_hash(chunks)

    if os.path.exists(EMBEDDING_CACHE):
        try:
            cache = np.load(EMBEDDING_CACHE, allow_pickle=False)
            if (
                str(cache["chunk_hash"]) == current_hash
                and str(cache["model"]) == EMBEDDING_MODEL
                and cache["embeddings"].shape[0] == len(chunks)
            ):
                print(f"Loaded embeddings from cache {cache['embeddings'].shape}")
                return cache["embeddings"]
            print("Embedding cache is outdated; rebuilding.")
        except Exception as exc:  # corrupt or incompatible cache
            print(f"Could not load embedding cache ({exc}); rebuilding.")

    embeddings = create_embeddings(client, chunks)

    os.makedirs(os.path.dirname(EMBEDDING_CACHE), exist_ok=True)
    np.savez(EMBEDDING_CACHE, embeddings=embeddings, chunk_hash=current_hash, model=EMBEDDING_MODEL)
    print(f"Embeddings saved to {EMBEDDING_CACHE} {embeddings.shape}")

    return embeddings


def embed_query(client, query):
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
    return np.array(response.data[0].embedding)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def semantic_search(chunks, embeddings, query_embedding, top_k=SEMANTIC_TOP_K):
    """Cosine similarity between the query and every chunk embedding."""
    doc_norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
    query_norm = np.linalg.norm(query_embedding) + 1e-10
    scores = (embeddings / doc_norms) @ (query_embedding / query_norm)

    indices = np.argsort(scores)[::-1][:top_k]
    return [
        {**chunks[i], "rank": rank, "score": float(scores[i]), "method": "Semantic"}
        for rank, i in enumerate(indices, start=1)
    ]


def tokenize(text):
    return TOKEN_PATTERN.findall(text.lower())


def build_bm25(chunks):
    return BM25Okapi([tokenize(chunk["text"]) for chunk in chunks])


def bm25_search(bm25, chunks, query, top_k=BM25_TOP_K):
    scores = bm25.get_scores(tokenize(query))
    indices = np.argsort(scores)[::-1][:top_k]
    return [
        {**chunks[i], "rank": rank, "score": float(scores[i]), "method": "BM25"}
        for rank, i in enumerate(indices, start=1)
    ]


def merge_candidates(*result_lists):
    """Union of several result lists; a chunk found by more than one method keeps both labels."""
    merged = {}
    for results in result_lists:
        for chunk in results:
            key = chunk["chunk_id"]
            if key in merged:
                merged[key]["method"] += " + " + chunk["method"]
            else:
                merged[key] = dict(chunk)
    return list(merged.values())


def rerank(reranker, query, candidates, top_k=RERANK_TOP_K):
    """Score each (query, chunk) pair with the Cross-Encoder and keep the best top_k."""
    scores = reranker.predict([(query, chunk["text"]) for chunk in candidates])
    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)

    return [
        {**chunk, "rank": rank, "rerank_score": float(score)}
        for rank, (chunk, score) in enumerate(ranked[:top_k], start=1)
    ]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_answer(client, query, evidence):
    context = "\n\n".join(
        f"[{chunk['citation']}]\n{chunk['text']}"
        for chunk in evidence
    )
    prompt = PROMPT_TEMPLATE.format(query=query, context=context)

    response = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    if not response.choices:
        error = getattr(response, "error", None)
        detail = f": {error}" if error else ""
        return f"The LLM provider returned no answer{detail}"

    content = response.choices[0].message.content
    return content or "The LLM returned empty content."


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_results(title, results):
    print(f"\n{SEPARATOR}\n{title}\n{SEPARATOR}")
    for result in results:
        score = result.get("rerank_score", result["score"])
        print(
            f"Rank {result['rank']} | Chunk {result['chunk_id']} | "
            f"{result['citation']} | Score {score:.4f} | {result['method']}"
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class RetrievalPipeline:
    """Loads the documents once, then answers any number of queries."""

    def __init__(self, client):
        self.client = client
        self.reranker = CrossEncoder(RERANKER_MODEL)

        print("\nReading PDFs...")
        self.chunks = []
        for source, path in DOCUMENTS.items():
            pages = read_pdf(path)
            label = SOURCE_LABELS[source]
            print(f"{label} ({SOURCE_NAMES[label]}): {len(pages)} pages")
            self.chunks += create_chunks(pages, source, start_id=len(self.chunks) + 1)
        print(f"Total chunks: {len(self.chunks)}")

        print("\nLoading embeddings...")
        self.embeddings = load_or_create_embeddings(client, self.chunks)
        self.bm25 = build_bm25(self.chunks)

    def retrieve(self, query, semantic_k=SEMANTIC_TOP_K, bm25_k=BM25_TOP_K, rerank_k=RERANK_TOP_K):
        """Run both retrievers and the reranker, returning every intermediate result."""
        query_embedding = embed_query(self.client, query)
        semantic_results = semantic_search(self.chunks, self.embeddings, query_embedding, semantic_k)
        bm25_results = bm25_search(self.bm25, self.chunks, query, bm25_k)
        candidates = merge_candidates(semantic_results, bm25_results)
        reranked = rerank(self.reranker, query, candidates, rerank_k)
        return {
            "semantic": semantic_results,
            "bm25": bm25_results,
            "candidates": len(candidates),
            "reranked": reranked,
        }

    def answer(self, query, verbose=True, **retrieve_kwargs):
        """Retrieve, optionally print the tables, and return {answer, evidence, ...}."""
        results = self.retrieve(query, **retrieve_kwargs)

        if verbose:
            print(f"\nUnique candidates for reranking: {results['candidates']}")
            print_results(f"SEMANTIC SEARCH - TOP {len(results['semantic'])}", results["semantic"])
            print_results(f"BM25 SEARCH - TOP {len(results['bm25'])}", results["bm25"])
            print_results(f"CROSS-ENCODER RERANKING - TOP {len(results['reranked'])}", results["reranked"])
            print(f"\n{SEPARATOR}\nGENERATING ANSWER...\n{SEPARATOR}")

        results["answer"] = generate_answer(self.client, query, results["reranked"])
        return results


def build_pipeline(api_key=None):
    """Create a ready pipeline; raises RuntimeError on missing key or documents."""
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")
    missing = [path for path in DOCUMENTS.values() if not os.path.exists(path)]
    if missing:
        raise RuntimeError("Missing source documents: " + ", ".join(missing))
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    return RetrievalPipeline(client)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-q", "--query", help="answer a single question and exit")
    parser.add_argument("--quiet", action="store_true", help="hide retrieval and reranking tables")
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"\n{SEPARATOR}\nDataLeak Retrieval Strategy Analyzer\n{SEPARATOR}")

    try:
        pipeline = build_pipeline()
    except RuntimeError as exc:
        sys.exit(f"{exc} See README.md > Quick start.")
    except Exception as exc:  # model download, API or file errors
        sys.exit(f"Could not start the pipeline: {exc}")

    if args.query:
        try:
            answer = pipeline.answer(args.query, verbose=not args.quiet)["answer"]
        except Exception as exc:
            sys.exit(f"Request failed: {exc}")
        print(f"\nAssistant:\n{answer}")
        return

    print("\nSystem ready. Ask questions about the provided documents. Type 'exit' to quit.")
    print("Citations: PDPL = Personal Data Protection Law, PDBIG = Personal Data Breach Incidents Procedural Guide.")
    while True:
        print("\n" + "-" * 60)
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if query.lower() in {"exit", "quit", "q"}:
            print("\nGoodbye.")
            break
        if not query:
            print("Please enter a question.")
            continue

        try:
            answer = pipeline.answer(query, verbose=not args.quiet)["answer"]
        except KeyboardInterrupt:
            print("\nCancelled.")
            continue
        except Exception as exc:
            print(f"\nRequest failed: {exc}")
            continue
        print(f"\nAssistant:\n{answer}")


if __name__ == "__main__":
    main()
