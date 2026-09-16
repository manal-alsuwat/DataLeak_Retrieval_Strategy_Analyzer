import os
import re
import hashlib
import numpy as np
import pymupdf
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder


# ============================================================
# Configuration
# ============================================================

API_KEY = os.getenv("OPENROUTER_API_KEY")

EMBEDDING_MODEL = "liquid/lfm-2.5-embedding-350m:free"

GENERATION_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

EMBEDDING_CACHE = "data/embeddings_cache.npz"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY
)

RERANKER = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)


# ============================================================
# PDF Processing
# ============================================================

def read_pdf(path):
    doc = pymupdf.open(path)
    pages = []

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text()

        if text.strip():
            pages.append({
                "page": page_number,
                "text": text
            })

    doc.close()
    return pages


def clean_text(text):
    text = re.sub(
        r"Document Classification:\s*Public",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^\s*Public\s*$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE
    )

    text = re.sub(
        r"^\s*\d+\s*$",
        "",
        text,
        flags=re.MULTILINE
    )

    text = re.sub(
        r"^\s*!\s*$",
        "",
        text,
        flags=re.MULTILINE
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def create_chunks(
    pages,
    source,
    chunk_size=1200,
    overlap=200
):
    chunks = []
    chunk_id = 1

    for page_data in pages:

        text = clean_text(
            page_data["text"]
        )

        if len(text) < 50:
            continue

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= 50:

                chunks.append({
                    "chunk_id": chunk_id,
                    "source": source,
                    "page": page_data["page"],
                    "text": chunk_text
                })

                chunk_id += 1

            if end >= len(text):
                break

            start = end - overlap

    return chunks


# ============================================================
# Embedding Cache
# ============================================================

def create_chunks_hash(chunks):
    """
    Create a unique hash based on the chunk text and
    embedding model.

    This helps detect if the documents/chunks changed.
    """

    content = EMBEDDING_MODEL

    for chunk in chunks:
        content += (
            str(chunk["chunk_id"])
            + chunk["source"]
            + str(chunk["page"])
            + chunk["text"]
        )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def create_embeddings(
    chunks,
    batch_size=10
):
    embeddings = []

    for start in range(
        0,
        len(chunks),
        batch_size
    ):

        batch = chunks[
            start:start + batch_size
        ]

        print(
            f"Creating embeddings "
            f"{start + 1}-"
            f"{min(start + batch_size, len(chunks))} "
            f"of {len(chunks)}..."
        )

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[
                chunk["text"]
                for chunk in batch
            ]
        )

        embeddings.extend(
            item.embedding
            for item in response.data
        )

    return np.array(embeddings)


def load_or_create_embeddings(chunks):
    """
    Load cached embeddings if they already exist
    and match the current chunks.

    Otherwise, create new embeddings and save them.
    """

    current_hash = create_chunks_hash(chunks)

    # --------------------------------------------------------
    # Try loading cache
    # --------------------------------------------------------

    if os.path.exists(EMBEDDING_CACHE):

        print(
            "\nEmbedding cache found."
        )

        try:

            cache = np.load(
                EMBEDDING_CACHE,
                allow_pickle=False
            )

            cached_embeddings = cache["embeddings"]

            cached_hash = str(
                cache["chunk_hash"]
            )

            cached_model = str(
                cache["model"]
            )

            # Check that cache matches current data
            if (
                cached_hash == current_hash
                and cached_model == EMBEDDING_MODEL
                and cached_embeddings.shape[0] == len(chunks)
            ):

                print(
                    "Loading embeddings from cache..."
                )

                print(
                    f"Embedding matrix shape: "
                    f"{cached_embeddings.shape}"
                )

                return cached_embeddings

            print(
                "Embedding cache is outdated."
            )

        except Exception as e:

            print(
                f"Could not load embedding cache: {e}"
            )

    # --------------------------------------------------------
    # Create new embeddings
    # --------------------------------------------------------

    print(
        "\nCreating new embeddings..."
    )

    embeddings = create_embeddings(
        chunks
    )

    # --------------------------------------------------------
    # Save cache
    # --------------------------------------------------------

    os.makedirs(
        os.path.dirname(EMBEDDING_CACHE),
        exist_ok=True
    )

    np.savez(
        EMBEDDING_CACHE,
        embeddings=embeddings,
        chunk_hash=current_hash,
        model=EMBEDDING_MODEL
    )

    print(
        f"Embeddings saved to: "
        f"{EMBEDDING_CACHE}"
    )

    print(
        f"Embedding matrix shape: "
        f"{embeddings.shape}"
    )

    return embeddings


def create_query_embedding(query):

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query]
    )

    return np.array(
        response.data[0].embedding
    )


# ============================================================
# Retrieval
# ============================================================

def semantic_search(
    chunks,
    embeddings,
    query_embedding,
    top_k=10
):

    embeddings_norm = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True
    )

    query_norm = np.linalg.norm(
        query_embedding
    )

    scores = np.dot(
        embeddings /
        (embeddings_norm + 1e-10),

        query_embedding /
        (query_norm + 1e-10)
    )

    indices = np.argsort(
        scores
    )[::-1][:top_k]

    results = []

    for rank, i in enumerate(
        indices,
        start=1
    ):

        results.append({
            **chunks[i],
            "rank": rank,
            "score": float(scores[i]),
            "method": "Semantic"
        })

    return results


def bm25_search(
    chunks,
    query,
    top_k=10
):

    documents = [
        chunk["text"].lower().split()
        for chunk in chunks
    ]

    bm25 = BM25Okapi(
        documents
    )

    scores = bm25.get_scores(
        query.lower().split()
    )

    indices = np.argsort(
        scores
    )[::-1][:top_k]

    results = []

    for rank, i in enumerate(
        indices,
        start=1
    ):

        results.append({
            **chunks[i],
            "rank": rank,
            "score": float(scores[i]),
            "method": "BM25"
        })

    return results


# ============================================================
# Cross-Encoder Reranking
# ============================================================

def rerank(
    query,
    candidates,
    top_k=5
):

    # Remove duplicate chunks
    unique_chunks = {}

    for chunk in candidates:
        unique_chunks[
            chunk["chunk_id"]
        ] = chunk

    candidates = list(
        unique_chunks.values()
    )

    pairs = [
        (
            query,
            chunk["text"]
        )
        for chunk in candidates
    ]

    scores = RERANKER.predict(
        pairs
    )

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True
    )

    results = []

    for rank, (
        chunk,
        score
    ) in enumerate(
        ranked[:top_k],
        start=1
    ):

        results.append({
            **chunk,
            "rank": rank,
            "rerank_score": float(score)
        })

    return results


# ============================================================
# Display Results
# ============================================================

def print_results(
    title,
    results
):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    for result in results:

        score = result.get(
            "rerank_score",
            result["score"]
        )

        print(
            f"Rank {result['rank']} | "
            f"Chunk {result['chunk_id']} | "
            f"Page {result['page']} | "
            f"Score {score:.4f} | "
            f"{result['method']}"
        )


# ============================================================
# LLM Generation
# ============================================================

def generate_answer(
    query,
    reranked_results
):

    context_parts = []

    for chunk in reranked_results:

        context_parts.append(
            f"[Chunk {chunk['chunk_id']} | "
            f"Page {chunk['page']}]\n"
            f"{chunk['text']}"
        )

    context = "\n\n".join(
        context_parts
    )

    prompt = f"""
You are a retrieval-based question answering assistant.

Answer the user's question using ONLY the evidence provided below.

Rules:
- Do not use outside knowledge.
- Do not invent information.
- If the evidence is insufficient, clearly say that the provided documents do not contain enough information.
- Give a concise and direct answer.
- Base the answer on the retrieved evidence.

Question:
{query}

Retrieved Evidence:
{context}
"""

    response = client.chat.completions.create(
        model=GENERATION_MODEL,

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0
    )

    # --------------------------------------------------------
    # Check OpenRouter response
    # --------------------------------------------------------

    if response.choices is None:

        print("\nERROR: LLM returned no choices.")

        print(
            "\nFull LLM response:"
        )

        print(response)

        return (
            "The LLM did not return a valid answer. "
            "Please check the model response above."
        )

    if len(response.choices) == 0:

        print("\nERROR: LLM returned an empty choices list.")

        print(
            "\nFull LLM response:"
        )

        print(response)

        return (
            "The LLM returned an empty response."
        )

    content = response.choices[0].message.content

    if not content:

        print("\nERROR: LLM returned empty content.")

        print(
            "\nFull LLM response:"
        )

        print(response)

        return (
            "The LLM returned empty content."
        )

    return content

# ============================================================
# Main
# ============================================================

# ============================================================
# Main - Live Chat
# ============================================================

def main():

    print("\n" + "=" * 60)
    print("DataLeak Retrieval Strategy Analyzer")
    print("=" * 60)

    print("\nLoading documents...")

    law_path = (
        "data/raw/"
        "PersonalDataProtectionLaw.pdf"
    )

    breach_path = (
        "data/raw/"
        "PersonalDataBreachIncidents.pdf"
    )

    # --------------------------------------------------------
    # Read PDFs
    # --------------------------------------------------------

    law_pages = read_pdf(
        law_path
    )

    breach_pages = read_pdf(
        breach_path
    )

    print(
        f"Law pages read: "
        f"{len(law_pages)}"
    )

    print(
        f"Breach guide pages read: "
        f"{len(breach_pages)}"
    )

    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    print("\nCreating chunks...")

    chunks = (
        create_chunks(
            law_pages,
            "PersonalDataProtectionLaw"
        )
        +
        create_chunks(
            breach_pages,
            "PersonalDataBreachIncidents"
        )
    )

    print(
        f"Total chunks: "
        f"{len(chunks)}"
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    print("\nLoading / Creating embeddings...")

    embeddings = load_or_create_embeddings(
        chunks
    )

    print("\nSystem ready.")

    print(
        "\nAsk questions about the provided documents."
    )

    print(
        "Type 'exit' to quit."
    )

    # ========================================================
    # LIVE CHAT
    # ========================================================

    while True:

        print("\n" + "-" * 60)

        query = input("You: ").strip()

        # Exit
        if query.lower() in [
            "exit",
            "quit",
            "q"
        ]:

            print(
                "\nGoodbye."
            )

            break

        # Empty input
        if not query:

            print(
                "Please enter a question."
            )

            continue

        # ----------------------------------------------------
        # Query Embedding
        # ----------------------------------------------------

        query_embedding = (
            create_query_embedding(
                query
            )
        )

        # ----------------------------------------------------
        # Semantic Retrieval
        # ----------------------------------------------------

        semantic_results = semantic_search(
            chunks,
            embeddings,
            query_embedding,
            top_k=10
        )

        # ----------------------------------------------------
        # BM25 Retrieval
        # ----------------------------------------------------

        bm25_results = bm25_search(
            chunks,
            query,
            top_k=10
        )

        # ----------------------------------------------------
        # Candidates
        # ----------------------------------------------------

        candidates = (
            semantic_results
            +
            bm25_results
        )

        print(
            f"\nCandidates before reranking: "
            f"{len(candidates)}"
        )

        # ----------------------------------------------------
        # Cross-Encoder Reranking
        # ----------------------------------------------------

        reranked_results = rerank(
            query,
            candidates,
            top_k=5
        )

        # ----------------------------------------------------
        # Retrieval Results
        # ----------------------------------------------------

        print_results(
            "SEMANTIC SEARCH - TOP 10",
            semantic_results
        )

        print_results(
            "BM25 SEARCH - TOP 10",
            bm25_results
        )

        print_results(
            "CROSS-ENCODER RERANKING - TOP 5",
            reranked_results
        )

        # ----------------------------------------------------
        # Generate Answer
        # ----------------------------------------------------

        print(
            "\n" + "=" * 60
        )

        print(
            "GENERATING ANSWER..."
        )

        print(
            "=" * 60
        )

        answer = generate_answer(
            query,
            reranked_results
        )

        # ----------------------------------------------------
        # Final Answer
        # ----------------------------------------------------

        print(
            "\nAssistant:"
        )

        print(
            answer
        )


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":

    main()

    print("\n" + "=" * 60)
    print(
        "DataLeak Retrieval Strategy Analyzer"
    )
    print("=" * 60)

    law_path = (
        "data/raw/"
        "PersonalDataProtectionLaw.pdf"
    )

    breach_path = (
        "data/raw/"
        "PersonalDataBreachIncidents.pdf"
    )

    # --------------------------------------------------------
    # Read PDFs
    # --------------------------------------------------------

    print("\nReading PDFs...")

    law_pages = read_pdf(
        law_path
    )

    breach_pages = read_pdf(
        breach_path
    )

    print(
        f"Law pages read: "
        f"{len(law_pages)}"
    )

    print(
        f"Breach guide pages read: "
        f"{len(breach_pages)}"
    )

    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    print("\nCreating chunks...")

    chunks = (
        create_chunks(
            law_pages,
            "PersonalDataProtectionLaw"
        )
        +
        create_chunks(
            breach_pages,
            "PersonalDataBreachIncidents"
        )
    )

    print(
        f"Total chunks: "
        f"{len(chunks)}"
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    print("\nLoading / Creating embeddings...")

    embeddings = load_or_create_embeddings(
        chunks
    )

    # --------------------------------------------------------
    # Query
    # --------------------------------------------------------

    query = (
        "What is personal data?"
    )

    print(
        f"\nQuery: {query}"
    )

    query_embedding = (
        create_query_embedding(
            query
        )
    )

    # --------------------------------------------------------
    # Semantic Retrieval
    # --------------------------------------------------------

    semantic_results = semantic_search(
        chunks,
        embeddings,
        query_embedding,
        top_k=10
    )

    # --------------------------------------------------------
    # BM25 Retrieval
    # --------------------------------------------------------

    bm25_results = bm25_search(
        chunks,
        query,
        top_k=10
    )

    # --------------------------------------------------------
    # Candidates
    # --------------------------------------------------------

    candidates = (
        semantic_results
        +
        bm25_results
    )

    print(
        f"\nCandidates before reranking: "
        f"{len(candidates)}"
    )

    # --------------------------------------------------------
    # Cross-Encoder
    # --------------------------------------------------------

    reranked_results = rerank(
        query,
        candidates,
        top_k=5
    )

    # --------------------------------------------------------
    # KEEP ALL PREVIOUS OUTPUTS
    # --------------------------------------------------------

    print_results(
        "SEMANTIC SEARCH - TOP 10",
        semantic_results
    )

    print_results(
        "BM25 SEARCH - TOP 10",
        bm25_results
    )

    print_results(
        "CROSS-ENCODER RERANKING - TOP 5",
        reranked_results
    )

    # --------------------------------------------------------
    # LLM Generation
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("GENERATING FINAL ANSWER")
    print("=" * 60)

    answer = generate_answer(
        query,
        reranked_results
    )

    print("\n" + "=" * 60)
    print("FINAL LLM ANSWER")
    print("=" * 60)

    print(answer)

    print("\n" + "=" * 60)
    print(
        "Retrieval + Reranking + Generation completed."
    )
    print("=" * 60)


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    main()