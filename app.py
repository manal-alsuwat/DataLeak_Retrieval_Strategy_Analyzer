"""Streamlit interface for the DataLeak Retrieval Strategy Analyzer.

Run with:
    python -m streamlit run app.py
"""

import html
import os
import time

import streamlit as st

import retrieval_debugger
from retrieval_debugger import (
    BM25_TOP_K,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    RERANK_TOP_K,
    RERANKER_MODEL,
    SEMANTIC_TOP_K,
    SOURCE_LABELS,
    SOURCE_NAMES,
    build_pipeline,
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DataLeak Retrieval Strategy Analyzer",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1100px; }
      .hero h1 { margin-bottom: 0.2rem; }
      .hero p  { color: #6b7280; margin-top: 0; }
      .cite {
        display: inline-block; padding: 2px 8px; margin: 2px 4px 2px 0;
        border-radius: 999px; background: rgba(99, 102, 241, 0.15);
        font-size: 0.78rem; font-weight: 600; white-space: nowrap;
      }
      .evidence {
        border: 1px solid rgba(128, 128, 128, 0.35); border-left: 4px solid #6366f1;
        border-radius: 6px; padding: 10px 14px; margin-bottom: 10px;
        background: rgba(99, 102, 241, 0.06); font-size: 0.9rem; line-height: 1.55;
      }
      .evidence .meta { opacity: 0.7; font-size: 0.78rem; margin-bottom: 4px; }
      div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 8px 12px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

SAMPLE_QUESTIONS = [
    "What is personal data according to Article 1?",
    "In which cases may personal data be processed without consent under Article 6?",
    "When must a Controller notify SDAIA about a personal data breach?",
    "What are the three stages for handling a personal data breach incident?",
    "What is the penalty for violating the Personal Data Protection Law?",
    "What is artificial intelligence?",
]


# ---------------------------------------------------------------------------
# Pipeline (loaded once per process)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading documents, embeddings and reranker…")
def get_pipeline(api_key, code_version):
    # code_version is the pipeline file's mtime, so edits to it trigger a reload.
    return build_pipeline(api_key)


def rows(results, score_key="score"):
    return [
        {
            "Rank": r["rank"],
            "Source": SOURCE_LABELS.get(r["source"], r["source"]),
            "Page": r["page"],
            "Articles": ", ".join(map(str, r["articles"])) or "—",
            "Score": round(r.get(score_key, r["score"]), 4),
            "Found by": r["method"],
            "Chunk": r["chunk_id"],
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Configuration")

    api_key = st.text_input(
        "OpenRouter API key",
        value=os.getenv("OPENROUTER_API_KEY", ""),
        type="password",
        help="Pre-filled from OPENROUTER_API_KEY if set. Used only for this session.",
    )

    st.subheader("Retrieval")
    semantic_k = st.slider("Semantic search · top k", 1, 20, SEMANTIC_TOP_K)
    bm25_k = st.slider("BM25 search · top k", 1, 20, BM25_TOP_K)
    rerank_k = st.slider("Reranked evidence · top k", 1, 10, RERANK_TOP_K)
    show_tables = st.toggle("Show retrieval tables", value=True)

    st.subheader("Source abbreviations")
    for abbr, name in SOURCE_NAMES.items():
        st.caption(f"**{abbr}** — {name}")

    st.subheader("Models")
    st.caption(f"**Embeddings**  \n`{EMBEDDING_MODEL}`")
    st.caption(f"**Reranker**  \n`{RERANKER_MODEL}`")
    st.caption(f"**Generation**  \n`{GENERATION_MODEL}`")

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.history = []
        st.rerun()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
      <h1>🔎 DataLeak Retrieval Strategy Analyzer</h1>
      <p>Grounded question answering over the Saudi Personal Data Protection Law (PDPL)
         and the Personal Data Breach Incidents Procedural Guide (PDBIG) — semantic search + BM25,
         Cross-Encoder reranking, and cited answers.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not api_key:
    st.info("Enter your OpenRouter API key in the sidebar to start.")
    st.stop()

try:
    pipeline = get_pipeline(api_key, os.path.getmtime(retrieval_debugger.__file__))
except Exception as exc:  # missing documents, bad key, network
    st.error(f"Could not initialise the pipeline: {exc}")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Documents", len(SOURCE_LABELS))
c2.metric("Chunks indexed", len(pipeline.chunks))
c3.metric("Embedding dimension", pipeline.embeddings.shape[1])

st.caption(
    "Citations use **PDPL** for the Personal Data Protection Law and "
    "**PDBIG** for the Personal Data Breach Incidents Procedural Guide."
)

# ---------------------------------------------------------------------------
# Sample questions
# ---------------------------------------------------------------------------

st.caption("Try one of the test questions:")
cols = st.columns(3)
for i, q in enumerate(SAMPLE_QUESTIONS):
    if cols[i % 3].button(q, key=f"sample_{i}"):
        st.session_state.pending = q

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []


def render_turn(turn):
    with st.chat_message("user"):
        st.write(turn["query"])

    with st.chat_message("assistant"):
        st.markdown(turn["answer"])

        cites = "".join(f'<span class="cite">{html.escape(r["citation"])}</span>' for r in turn["reranked"])
        st.markdown(f"**Sources used:** {cites}", unsafe_allow_html=True)
        st.caption(f"Answered in {turn['elapsed']:.1f}s · {turn['candidates']} unique candidates reranked")

        with st.expander("Evidence passed to the model"):
            for r in turn["reranked"]:
                meta = (
                    f'#{r["rank"]} · {r["citation"]} · rerank score {r["rerank_score"]:.3f}'
                    f' · found by {r["method"]}'
                )
                # Keep the whole block on one line: a blank line would end the HTML
                # block and let Markdown reformat the rest of the passage.
                body = html.escape(r["text"]).replace("\n", "<br>")
                st.markdown(
                    f'<div class="evidence"><div class="meta">{html.escape(meta)}</div>{body}</div>',
                    unsafe_allow_html=True,
                )

        if show_tables:
            with st.expander("Retrieval strategy comparison"):
                t1, t2, t3 = st.tabs(["Semantic search", "BM25 search", "Cross-Encoder reranking"])
                t1.dataframe(rows(turn["semantic"]), hide_index=True)
                t2.dataframe(rows(turn["bm25"]), hide_index=True)
                t3.dataframe(rows(turn["reranked"], "rerank_score"), hide_index=True)


for turn in st.session_state.history:
    render_turn(turn)

query = st.chat_input("Ask a question about the documents…")
if "pending" in st.session_state:
    query = st.session_state.pop("pending")

if query:
    with st.chat_message("user"):
        st.write(query)
    with st.chat_message("assistant"):
        with st.spinner("Retrieving, reranking and generating…"):
            start = time.perf_counter()
            try:
                results = pipeline.answer(
                    query, verbose=False,
                    semantic_k=semantic_k, bm25_k=bm25_k, rerank_k=rerank_k,
                )
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                st.stop()
            results["query"] = query
            results["elapsed"] = time.perf_counter() - start

    st.session_state.history.append(results)
    st.rerun()
