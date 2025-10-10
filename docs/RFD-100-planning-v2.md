# Design Doc: Open-Source PDF + Image Embeddings for RAG

**Author:** Wentao  
**Date:** 2025-10-09  
**Status:** Draft → Adopt

---

## 1) Goal

Enable **retrieval-augmented generation (RAG)** over PDFs where **both text and images (figures, charts, screenshots, equations)** are embedded into a **single searchable vector space** and returned with precise page/bounding-box grounding.

---

## 2) Scope & Constraints

- **Scope:** Parsing PDFs → chunking text & extracting figures → embedding (text + images) → vector index → text-query retrieval → optional re-ranking → LLM answer with grounded citations.
- **Constraints:**
  - **Open-source models only** (no hosted/proprietary APIs).
  - Input PDFs will be converted with **Docling** or **Markit**.
  - Must support **direct image search** (not just caption-only).
  - Reasonable local inference (single workstation/GPU).

---

## 3) Requirements

- **R1: Multimodal retrieval** — Text queries must retrieve both text chunks and image figures.
- **R2: Unified space** — Prefer a **single embedding space** for text+image to simplify scoring and ranking.
- **R3: High recall on technical content** — tables, plots, equations.
- **R4: Grounding** — return `doc_id`, `page`, and `bbox` to preview source context.
- **R5: Efficiency** — scalable indexing (FAISS/LanceDB), batchable inference.
- **R6: Open-source only** — reproducible, offline.

---

## 4) Options Considered (Open-Source)

| Option | Modality | Pros | Cons | Verdict |
|---|---|---|---|---|
| **E5-V (intfloat/e5-v)** | Text + Image (same space) | Unified embedding for text & images; strong multimodal retrieval | Heavier than pure text encoders | **Chosen** (default) |
| **bge-m3 + SigLIP/OpenCLIP** (late fusion) | Text (bge) + Image (SigLIP/CLIP) | Best-in-class text retrieval; fast image encoders | Two spaces; fusion tuning; more plumbing | Backup |
| **Jina Embeddings v3** | Text (+layout-aware) | Lightweight; great on HTML/Markdown | No native image embeddings | For text-only corpora |
| **MiniCPM-V 2.6/2.8** | Text + Image | Good vision-language; local | Not optimized as a pure embedder | Experimental |
| **InternVL 2.0** | Text + Image | Very strong doc/chart understanding | Heavy; slower for large-scale indexing | Research only |

---

## 5) Decision (Conclusion & Recommendation)

- **Primary:** Use **E5-V** for a **single joint embedding space** covering **text + images**, enabling simple cosine similarity retrieval over a single index.
- **Fallback:** If throughput constraints or custom scoring are needed, use **bge-m3 (text)** + **SigLIP/OpenCLIP (image)** with **late fusion** scoring.

Rationale: E5-V preserves simplicity (one model, one index, one score) while meeting the multimodal retrieval requirement (R1–R3) and staying open-source (R6).

---

## 6) Target Architecture

1. **Parse:**  
   - PDF → **Docling** (preferred for HTML/Markdown + coords) or **Markit**.  
   - Produce structured blocks: `paragraphs`, `headings`, `tables`, `captions`, `figures` (image files), each with `doc_id`, `page`, `bbox`.

2. **Preprocess:**  
   - **Chunk text** by structure (H1/H2, paragraphs, table boundaries).  
   - Extract figures to PNG/JPG; link to nearest caption.  
   - Optional OCR on figures/screenshots to create auxiliary text.

3. **Embed (E5-V):**  
   - Text chunks → vectors.  
   - Images (raw pixels) → vectors.  
   - (Optional) Caption/OCR text → vectors (stored as separate items).

4. **Index:**  
   - **FAISS** (HNSW) *or* **LanceDB**.  
   - Single index (cosine over L2-normalized vectors).  
   - Store rich metadata: `doc_id`, `page`, `bbox`, `section`, `kind={text|image|caption}`, `path`.

5. **Query:**  
   - Incoming user text → E5-V query vector.  
   - Search unified index → top-k mixed (text + image) hits.  
   - Optional lightweight **cross-encoder** re-rank or LLM semantic re-rank on top-k.

6. **Answering:**  
   - Render previews using `page` + `bbox`.  
   - Provide LLM with retrieved **mixed context** (text spans + image captions/OCR text) for grounded responses.

---

## 7) Implementation Details

### 7.1 Chunking (text)
- **Size:** ~800–1200 tokens, **overlap:** 50–100.
- Respect section boundaries; keep table cells together; strip headers/footers.
- Merge small captions with nearby text chunk (for context), but also store caption as a separate record when embedding images.

### 7.2 Images
- Extract per figure (and table renders if applicable).
- Keep **caption link** (`caption_id`) and **cross-refs** (“Fig. 3”, “Table 2”).
- **Deduplicate** via perceptual hash to prevent index bloat.

### 7.3 Indexing
- Normalize embeddings (L2) and use **cosine** (inner product on normalized vectors).
- Suggested FAISS config: `HNSW32,Flat` for balance of recall/latency.
- Keep a **metadata store** (e.g., SQLite/Parquet within LanceDB) to join vector IDs to source info.

### 7.4 Scoring
- **Unified (default):** `score = cosine(q_vec, item_vec)` across both text and images.  
- **Late fusion (fallback stack):**  
  `score = w_text * cosine(bge(q), bge(text)) + w_img * cosine(siglip(q), siglip(img))`  
  Tune `w_text`, `w_img` on a labeled dev set.

---

## 8) Quality, Evaluation & Monitoring

- **Offline eval set:** 100–300 text queries with gold references to pages/figures.
- **Metrics:** Recall@k (k∈{5,10,20}), nDCG@10, MRR, time/query, GPU utilization.
- **Ablations:**  
  - Text-only vs text+image,  
  - With/without captions/OCR,  
  - Chunk sizes & overlap,  
  - FAISS HNSW parameters (M, efSearch).
- **Regression suite:** Lock model checkpoint & preprocessing to detect drift.

---

## 9) Operational Considerations

- **Hardware:** 16–24 GB GPU recommended for E5-V batch inference.  
- **Throughput:** Batch encode (32–128), pre-compute & persist vectors; incremental indexing on new docs.  
- **Repro:** Pin model revision/checkpoint; record preprocessor versions (Docling/Markit).  
- **Privacy:** All local/offline; no external calls.

---

## 10) Minimal Pseudocode (E5-V, single index)

    # Load model
    model = SentenceTransformer("intfloat/e5-v")  # text + image joint space

    # Embed text chunks
    text_vecs = [model.encode(txt, normalize_embeddings=True) for txt in text_chunks]

    # Embed images
    imgs = [Image.open(p).convert("RGB") for p in image_paths]
    img_vecs = [model.encode(img, normalize_embeddings=True) for img in imgs]

    # Build FAISS (cosine via inner product on normalized vectors)
    dim = text_vecs[0].shape[0]
    index = faiss.index_factory(dim, "HNSW32,Flat", faiss.METRIC_INNER_PRODUCT)
    all_vecs = np.vstack(text_vecs + img_vecs).astype("float32")
    index.add(all_vecs)

    # Query
    qv = model.encode(query_text, normalize_embeddings=True).astype("float32")
    D, I = index.search(qv[None, :], top_k)

---

## 11) Risks & Mitigations

- **R-01 Image-only content under-retrieved** → Add captions/OCR as auxiliary text items; keep both image and caption embeddings.  
- **R-02 Index bloat from near-duplicates** → Perceptual hash dedup; collapse similar vectors by doc/page.  
- **R-03 Latency** → Increase HNSW efSearch gradually; pre-warm caches; batch encode; optional GPU FAISS.  
- **R-04 Mis-grounding** → Always carry `page` + `bbox`; highlight exact region in UI.

---

## 12) Roadmap / Next Steps

1. **Prototype** E5-V pipeline on 5–10 representative PDFs.  
2. Build **dev eval set** (≥150 labeled queries; include figure-heavy questions).  
3. Tune **chunking** & **HNSW** params; decide on captions/OCR inclusion.  
4. Add **optional re-ranker** (cross-encoder) if needed for precision@5.  
5. Productionize: streaming index updates, monitoring, regression tests.

---

## Final Recommendation

Adopt **E5-V** as the **default open-source multimodal embedding model** to index **both text and images** from Docling/Markit-parsed PDFs into a **single FAISS/LanceDB index** with cosine similarity.  
Keep a **fallback dual-space** path (**bge-m3 + SigLIP/OpenCLIP**) with late fusion for scenarios requiring maximum text retrieval quality or higher image throughput.
