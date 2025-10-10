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

---

# FastAPI Web Service Implementation Plan

**Status:** Implementation Ready
**Integration:** DocEater Codebase
**Timeline:** 4 weeks (MVP)

## Web Service Architecture

### Core Features
1. **PDF Upload API** - Accept PDF uploads, process with existing Docling pipeline
2. **Multimodal Embeddings** - Use E5-V model for unified text+image embedding space
3. **Vector Storage** - FAISS index for fast similarity search
4. **RAG Search API** - Query endpoint returning grounded text+image results
5. **Document Management** - List, retrieve, delete processed documents

### Integration with Existing DocEater
The existing codebase provides 90% of required functionality:
- ✅ **Document Processing**: `processor.py` + `docling_wrapper.py`
- ✅ **Image Extraction**: `image_storage.py`
- ✅ **Database Layer**: `database.py` + `models.py`
- ✅ **Configuration**: `config.py` with Pydantic settings

New components to add:
- 🆕 **FastAPI Web Layer**
- 🆕 **Embedding Service** (E5-V)
- 🆕 **Vector Store** (FAISS)
- 🆕 **RAG Retrieval Logic**

### Directory Structure
```
src/doceater/
├── api/                     # NEW: FastAPI web service
│   ├── __init__.py
│   ├── main.py             # FastAPI app setup
│   ├── routes/             # API endpoints
│   │   ├── __init__.py
│   │   ├── documents.py    # Document upload/processing
│   │   ├── search.py       # RAG search endpoints
│   │   └── health.py       # Health checks
│   ├── models/             # API request/response models
│   │   ├── __init__.py
│   │   ├── requests.py     # Pydantic request models
│   │   └── responses.py    # Pydantic response models
│   └── dependencies.py     # FastAPI dependencies
├── embeddings/             # NEW: Embedding & RAG system
│   ├── __init__.py
│   ├── embedder.py         # E5-V embedding service
│   ├── vector_store.py     # FAISS/LanceDB vector storage
│   ├── chunker.py          # Text chunking logic
│   └── retriever.py        # RAG retrieval logic
└── (existing files...)
```

## API Endpoints Design

### Document Management
```
POST /api/v1/documents/upload
- Upload PDF file
- Returns: document_id, processing_status

GET /api/v1/documents/{document_id}
- Get document details + processing status
- Returns: metadata, text content, image list

GET /api/v1/documents
- List all documents with pagination
- Query params: status, limit, offset

DELETE /api/v1/documents/{document_id}
- Remove document and all associated data
```

### Search & Retrieval
```
POST /api/v1/search
- RAG search query
- Body: {"query": "text", "top_k": 10, "include_images": true}
- Returns: ranked results with text chunks + images + grounding

GET /api/v1/documents/{document_id}/embeddings
- Get embeddings for specific document
- Returns: text_embeddings[], image_embeddings[]

GET /api/v1/images/{image_id}
- Serve image files with proper headers
- Support for different formats and sizes
```

### System Management
```
GET /api/v1/health
- System health check
- Returns: database status, model status, disk usage

GET /api/v1/stats
- System statistics
- Returns: document count, embedding count, search metrics
```

## Data Flow Architecture

### Document Processing Pipeline
```
1. PDF Upload → FastAPI
2. Save to temp location
3. Trigger existing DocEater processor
4. Extract text chunks + images (existing pipeline)
5. Generate embeddings with E5-V
6. Store in FAISS index + database
7. Return document_id

Search Query:
1. Text query → E5-V embedding
2. FAISS similarity search
3. Retrieve mixed text+image results
4. Return with grounding info (page, bbox)
```

## Database Schema Extensions

### New Tables for Embeddings
```sql
-- Text chunk embeddings
CREATE TABLE text_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding_vector BYTEA NOT NULL,  -- Serialized numpy array
    page_number INTEGER,
    bbox_coordinates JSONB,           -- [x1, y1, x2, y2]
    section_title TEXT,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_text_embeddings_document_id (document_id),
    INDEX idx_text_embeddings_page (page_number)
);

-- Image embeddings
CREATE TABLE image_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_image_id UUID NOT NULL REFERENCES document_images(id) ON DELETE CASCADE,
    embedding_vector BYTEA NOT NULL,
    caption TEXT,
    ocr_text TEXT,                    -- Optional OCR for better retrieval
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_image_embeddings_document_image_id (document_image_id)
);

-- Vector index metadata
CREATE TABLE vector_indices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    index_name VARCHAR(100) NOT NULL UNIQUE,
    index_type VARCHAR(50) NOT NULL,  -- 'faiss_hnsw', 'lancedb', etc.
    dimension INTEGER NOT NULL,
    total_vectors INTEGER DEFAULT 0,
    index_path TEXT,
    model_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Response Format Specification

### Search Results
```json
{
  "query": "machine learning algorithms",
  "total_results": 25,
  "search_time_ms": 150,
  "results": [
    {
      "type": "text",
      "content": "Machine learning algorithms can be categorized...",
      "score": 0.89,
      "document_id": "uuid-123",
      "document_title": "ML Handbook.pdf",
      "page": 15,
      "bbox": [100, 200, 400, 300],
      "section": "Chapter 3: Algorithms",
      "chunk_index": 42
    },
    {
      "type": "image",
      "image_url": "/api/v1/images/uuid-456",
      "thumbnail_url": "/api/v1/images/uuid-456?size=thumbnail",
      "caption": "Figure 3.1: Decision Tree Example",
      "ocr_text": "Decision Tree Classification Accuracy: 94.2%",
      "score": 0.85,
      "document_id": "uuid-123",
      "document_title": "ML Handbook.pdf",
      "page": 16,
      "bbox": [50, 100, 500, 400],
      "image_type": "diagram"
    }
  ]
}
```

### Document Details
```json
{
  "document_id": "uuid-123",
  "filename": "research-paper.pdf",
  "title": "Advanced Machine Learning Techniques",
  "status": "completed",
  "file_size": 2048576,
  "page_count": 45,
  "processing_time_seconds": 68.5,
  "text_chunks": 156,
  "images_extracted": 23,
  "embeddings_generated": 179,
  "created_at": "2025-01-10T14:30:00Z",
  "processed_at": "2025-01-10T14:31:08Z",
  "metadata": {
    "author": "Dr. Jane Smith",
    "subject": "Machine Learning",
    "keywords": ["neural networks", "deep learning", "classification"]
  }
}
```

---

# Large File Handling Strategy (Up to 100MB)

## 🎯 **Target & Approach**

**Target File Size**: Up to 100MB PDFs
**Approach**: Streaming upload with memory-efficient processing
**Rationale**: Simple, clean, and sufficient for 95% of document use cases

## 📊 **Technical Implementation**

### **Streaming Upload Pattern**
```python
# Clean, memory-efficient approach
@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    # Validate file type and size early
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files supported")

    # Stream to temporary file (constant memory usage)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name

            # Stream in 64KB chunks (memory efficient)
            total_size = 0
            while chunk := await file.read(65536):  # 64KB chunks
                total_size += len(chunk)

                # Validate size during upload (fail fast)
                if total_size > 100 * 1024 * 1024:  # 100MB
                    raise HTTPException(413, "File too large")

                temp_file.write(chunk)

        # Process using existing DocEater pipeline
        document_id = await process_document_from_path(temp_path)
        return {"document_id": document_id, "status": "processing"}

    finally:
        # Always cleanup temporary file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
```

### **Server Configuration**
```python
# Uvicorn configuration for 100MB files
uvicorn.run(
    "doceater.api.main:app",
    host="0.0.0.0",
    port=8000,
    timeout_keep_alive=300,      # 5 minutes
    limit_max_requests=1000,
    access_log=True
)

# If using Nginx reverse proxy
# client_max_body_size 100M;
# proxy_read_timeout 300s;
# proxy_send_timeout 300s;
```

### **Memory Usage Profile**
- **Peak Memory**: ~64KB (chunk size) + DocEater processing overhead
- **Disk Usage**: 2x file size during processing (original + extracted content)
- **Processing Time**: ~30-60 seconds for 100MB PDF (depends on complexity)

## 🔧 **Configuration Settings**

```python
# Add to src/doceater/config.py
class Settings(BaseSettings):
    # File upload settings (optimized for 100MB)
    upload_max_size_mb: int = Field(default=100, description="Maximum upload size in MB")
    upload_chunk_size_kb: int = Field(default=64, description="Upload chunk size in KB")
    upload_timeout_seconds: int = Field(default=300, description="Upload timeout (5 minutes)")
    temp_upload_dir: str = Field(
        default_factory=lambda: str(Path.home() / "doceater_data" / "temp"),
        description="Temporary upload directory"
    )
    cleanup_temp_files: bool = Field(default=True, description="Auto-cleanup temp files")
```

## ✅ **Benefits of This Approach**

1. **Memory Efficient**: Constant 64KB memory usage regardless of file size
2. **Simple Implementation**: Uses standard FastAPI patterns, no complex chunking
3. **Fast Failure**: Validates file size during upload, not after
4. **Clean Integration**: Works seamlessly with existing DocEater processor
5. **Reliable Cleanup**: Guaranteed temporary file cleanup with try/finally
6. **Production Ready**: Handles timeouts, errors, and edge cases

## 🚫 **What We're NOT Implementing**

- **Resumable Uploads**: Not needed for 100MB files (upload time ~30-60 seconds)
- **Progress Tracking**: Simple enough to complete without user feedback
- **Multiple Chunk Endpoints**: Single endpoint keeps API simple
- **External Storage**: Local processing is sufficient for this scale

## 📈 **Performance Expectations**

| File Size | Upload Time | Processing Time | Total Time |
|-----------|-------------|-----------------|------------|
| 10MB      | 5-10 sec    | 10-20 sec      | 15-30 sec  |
| 50MB      | 15-30 sec   | 30-45 sec      | 45-75 sec  |
| 100MB     | 30-60 sec   | 45-90 sec      | 75-150 sec |

*Times assume decent internet connection (10+ Mbps) and modern hardware*

---

# Implementation Phases & TODO Lists

## Phase 1: Basic API Infrastructure (Week 1)

### 🎯 **Goal**: Set up FastAPI foundation with basic document operations

### **Dependencies & Setup**
- [ ] Add FastAPI dependencies to `pyproject.toml`
  - [ ] `fastapi>=0.104.0`
  - [ ] `uvicorn[standard]>=0.24.0`
  - [ ] `python-multipart>=0.0.6`
  - [ ] `sentence-transformers>=2.2.2`
  - [ ] `faiss-cpu>=1.7.4`
  - [ ] `numpy>=1.24.0`
- [ ] Run `uv sync` to install new dependencies
- [ ] Update `.env.example` with API configuration

### **Core API Structure**
- [ ] Create `src/doceater/api/` directory structure
- [ ] Implement `src/doceater/api/__init__.py`
- [ ] Implement `src/doceater/api/main.py` - FastAPI app setup
  - [ ] CORS configuration
  - [ ] Exception handlers
  - [ ] Middleware setup
  - [ ] Lifespan events
- [ ] Implement `src/doceater/api/dependencies.py`
  - [ ] Database dependency injection
  - [ ] Settings dependency
  - [ ] Authentication helpers (future)

### **API Models**
- [ ] Create `src/doceater/api/models/` directory
- [ ] Implement `src/doceater/api/models/requests.py`
  - [ ] `DocumentUploadRequest`
  - [ ] `SearchRequest`
  - [ ] `PaginationRequest`
- [ ] Implement `src/doceater/api/models/responses.py`
  - [ ] `DocumentResponse`
  - [ ] `DocumentListResponse`
  - [ ] `UploadResponse`
  - [ ] `ErrorResponse`
  - [ ] `HealthResponse`

### **Basic Routes**
- [ ] Create `src/doceater/api/routes/` directory
- [ ] Implement `src/doceater/api/routes/health.py`
  - [ ] `GET /api/v1/health` - System health check
  - [ ] `GET /api/v1/stats` - Basic statistics
- [ ] Implement `src/doceater/api/routes/documents.py`
  - [ ] `POST /api/v1/documents/upload` - File upload endpoint
  - [ ] `GET /api/v1/documents/{document_id}` - Get document details
  - [ ] `GET /api/v1/documents` - List documents with pagination
  - [ ] `DELETE /api/v1/documents/{document_id}` - Delete document

### **Configuration Updates**
- [ ] Extend `src/doceater/config.py` with API settings
  - [ ] `api_host: str = "0.0.0.0"`
  - [ ] `api_port: int = 8000`
  - [ ] `api_workers: int = 1`
  - [ ] `upload_max_size_mb: int = 100`
  - [ ] `upload_chunk_size_kb: int = 64`  # 64KB chunks for streaming
  - [ ] `upload_timeout_seconds: int = 300`  # 5 minutes
  - [ ] `cors_origins: list[str] = ["*"]`

### **Large File Handling (Up to 100MB)**
- [ ] Implement streaming upload in `src/doceater/api/routes/documents.py`
  - [ ] Use FastAPI's `UploadFile` with chunked reading
  - [ ] Stream directly to temporary file (avoid loading into memory)
  - [ ] Validate file size during upload (not after)
  - [ ] Clean up temporary files on success/failure
- [ ] Configure server limits for 100MB files
  - [ ] Set appropriate request timeouts
  - [ ] Configure memory-efficient file handling
  - [ ] Add progress tracking for large uploads

### **CLI Integration**
- [ ] Add API server command to `src/doceater/cli.py`
  - [ ] `doceat serve` - Start FastAPI server
  - [ ] `doceat serve --host 0.0.0.0 --port 8000`

### **Testing & Validation**
- [ ] Create basic API tests in `tests/api/`
- [ ] Test file upload functionality with various sizes (1MB, 10MB, 50MB, 100MB)
- [ ] Test upload timeout and error handling
- [ ] Test document CRUD operations
- [ ] Test health endpoints
- [ ] Verify integration with existing DocEater processor
- [ ] Test temporary file cleanup on success and failure

### **Documentation**
- [ ] Create API documentation with FastAPI auto-docs
- [ ] Add usage examples to README
- [ ] Document environment variables

---

## Phase 2: Embedding System (Week 2)

### 🎯 **Goal**: Implement E5-V embedding generation for text and images

### **Embedding Infrastructure**
- [ ] Create `src/doceater/embeddings/` directory
- [ ] Implement `src/doceater/embeddings/__init__.py`
- [ ] Implement `src/doceater/embeddings/embedder.py`
  - [ ] `EmbeddingService` class
  - [ ] E5-V model loading and initialization
  - [ ] Text embedding generation
  - [ ] Image embedding generation
  - [ ] Batch processing support
  - [ ] GPU detection and utilization
  - [ ] Model caching and memory management

### **Text Chunking System**
- [ ] Implement `src/doceater/embeddings/chunker.py`
  - [ ] `TextChunker` class
  - [ ] Markdown-aware chunking (respect headers, sections)
  - [ ] Configurable chunk size (800-1200 tokens)
  - [ ] Overlap handling (50-100 tokens)
  - [ ] Table preservation logic
  - [ ] Section boundary respect
  - [ ] Metadata preservation (page, bbox, section)

### **Database Schema Migration**
- [ ] Create Alembic migration for embedding tables
  - [ ] `text_embeddings` table
  - [ ] `image_embeddings` table
  - [ ] `vector_indices` table
- [ ] Update `src/doceater/models.py` with new models
  - [ ] `TextEmbedding` SQLAlchemy model
  - [ ] `ImageEmbedding` SQLAlchemy model
  - [ ] `VectorIndex` SQLAlchemy model
- [ ] Update `src/doceater/database.py` with embedding operations
  - [ ] `store_text_embedding()`
  - [ ] `store_image_embedding()`
  - [ ] `get_embeddings_by_document()`
  - [ ] `delete_embeddings_by_document()`

### **Integration with Document Processor**
- [ ] Update `src/doceater/processor.py`
  - [ ] Add embedding generation step
  - [ ] Integrate text chunking
  - [ ] Handle embedding storage
  - [ ] Error handling for embedding failures
  - [ ] Progress tracking for long documents

### **Configuration & Settings**
- [ ] Extend `src/doceater/config.py` with embedding settings
  - [ ] `embedding_model: str = "intfloat/e5-v"`
  - [ ] `embedding_device: str = "auto"`  # auto, cpu, cuda
  - [ ] `embedding_batch_size: int = 32`
  - [ ] `chunk_size_tokens: int = 1000`
  - [ ] `chunk_overlap_tokens: int = 100`
  - [ ] `enable_image_ocr: bool = False`

### **Embedding API Endpoints**
- [ ] Add embedding routes to `src/doceater/api/routes/documents.py`
  - [ ] `GET /api/v1/documents/{document_id}/embeddings`
  - [ ] `POST /api/v1/documents/{document_id}/reprocess-embeddings`

### **Testing & Validation**
- [ ] Test E5-V model loading and inference
- [ ] Test text chunking with various document types
- [ ] Test embedding generation pipeline
- [ ] Validate embedding storage and retrieval
- [ ] Performance testing with large documents
- [ ] Memory usage monitoring

### **Error Handling & Monitoring**
- [ ] Embedding generation error handling
- [ ] Model loading failure recovery
- [ ] Memory overflow protection
- [ ] Progress tracking for long operations
- [ ] Logging for debugging and monitoring

---

## Phase 3: Vector Search System (Week 3)

### 🎯 **Goal**: Implement FAISS-based vector similarity search

### **Vector Store Implementation**
- [ ] Implement `src/doceater/embeddings/vector_store.py`
  - [ ] `VectorStore` abstract base class
  - [ ] `FAISSVectorStore` implementation
  - [ ] Index creation and management
  - [ ] Vector addition and removal
  - [ ] Similarity search functionality
  - [ ] Index persistence and loading
  - [ ] Metadata mapping and retrieval

### **FAISS Configuration**
- [ ] Implement FAISS index factory setup
  - [ ] HNSW32,Flat configuration (from RFD-100)
  - [ ] Cosine similarity via inner product
  - [ ] Index parameter tuning (M=32, efSearch=64)
  - [ ] Memory mapping for large indices
  - [ ] Index backup and recovery

### **Search & Retrieval Logic**
- [ ] Implement `src/doceater/embeddings/retriever.py`
  - [ ] `RAGRetriever` class
  - [ ] Query embedding generation
  - [ ] Vector similarity search
  - [ ] Result ranking and filtering
  - [ ] Metadata enrichment
  - [ ] Result deduplication
  - [ ] Cross-modal result mixing (text + images)

### **Search API Implementation**
- [ ] Create `src/doceater/api/routes/search.py`
  - [ ] `POST /api/v1/search` - Main search endpoint
  - [ ] `POST /api/v1/search/similar` - Find similar documents
  - [ ] `GET /api/v1/search/suggestions` - Query suggestions
- [ ] Implement search request/response models
  - [ ] `SearchRequest` with query, filters, pagination
  - [ ] `SearchResponse` with results and metadata
  - [ ] `SearchResult` with grounding information

### **Index Management**
- [ ] Implement index lifecycle management
  - [ ] Index creation on first document
  - [ ] Incremental index updates
  - [ ] Index rebuilding for schema changes
  - [ ] Index optimization and compaction
  - [ ] Multiple index support (future)

### **Performance Optimization**
- [ ] Implement search result caching
- [ ] Query preprocessing and normalization
- [ ] Batch search support
- [ ] Search result pagination
- [ ] Memory usage optimization
- [ ] Search latency monitoring

### **Integration & Testing**
- [ ] Integrate vector search with document processing
- [ ] Test search accuracy with sample documents
- [ ] Performance testing with large document sets
- [ ] Test index persistence and recovery
- [ ] Validate search result grounding
- [ ] Cross-modal search testing (text query → image results)

### **Configuration Updates**
- [ ] Add vector search settings to `src/doceater/config.py`
  - [ ] `vector_index_type: str = "faiss_hnsw"`
  - [ ] `vector_index_path: str = "~/doceater_data/indices"`
  - [ ] `search_top_k_default: int = 10`
  - [ ] `search_top_k_max: int = 100`
  - [ ] `enable_search_cache: bool = True`
  - [ ] `search_cache_ttl_seconds: int = 300`

---

## Phase 4: RAG Enhancement & Production (Week 4)

### 🎯 **Goal**: Polish RAG system with advanced features and production readiness

### **Advanced Search Features**
- [ ] Implement result re-ranking
  - [ ] Cross-encoder re-ranking (optional)
  - [ ] Semantic similarity boosting
  - [ ] Recency scoring
  - [ ] Document authority scoring
- [ ] Add search filters and facets
  - [ ] Document type filtering
  - [ ] Date range filtering
  - [ ] Author/source filtering
  - [ ] Content type filtering (text vs images)

### **Image Serving & Management**
- [ ] Implement image serving endpoints
  - [ ] `GET /api/v1/images/{image_id}` - Full resolution
  - [ ] `GET /api/v1/images/{image_id}?size=thumbnail` - Thumbnails
  - [ ] `GET /api/v1/images/{image_id}?size=preview` - Preview size
- [ ] Add image processing capabilities
  - [ ] Thumbnail generation
  - [ ] Image format conversion
  - [ ] Image compression
  - [ ] Watermarking (optional)

### **Enhanced Grounding & Context**
- [ ] Improve result grounding information
  - [ ] Precise bounding box coordinates
  - [ ] Page preview generation
  - [ ] Context window expansion
  - [ ] Related content suggestions
- [ ] Add citation and reference tracking
  - [ ] Source document linking
  - [ ] Cross-reference detection
  - [ ] Citation formatting

### **Performance & Scalability**
- [ ] Implement search result caching
  - [ ] In-memory cache for frequent queries
  - [ ] Embedding cache for repeated documents
  - [ ] Result cache with TTL
- [ ] Optimize database queries
  - [ ] Query optimization for large document sets
  - [ ] Connection pooling configuration
  - [ ] Index optimization for search performance
- [ ] File upload optimization
  - [ ] Validate upload performance with 100MB files
  - [ ] Optimize temporary file handling
  - [ ] Monitor disk space usage during processing

### **Security & Authentication**
- [ ] Implement API authentication
  - [ ] API key authentication
  - [ ] JWT token support
  - [ ] Rate limiting per user/key
- [ ] Add access control
  - [ ] Document-level permissions
  - [ ] User role management
  - [ ] Audit logging
- [ ] Security hardening
  - [ ] Input validation and sanitization
  - [ ] File upload security
  - [ ] CORS configuration
  - [ ] Security headers

### **Monitoring & Observability**
- [ ] Add comprehensive logging
  - [ ] Structured logging with JSON
  - [ ] Search query logging
  - [ ] Performance metrics logging
  - [ ] Error tracking and alerting
- [ ] Implement metrics collection
  - [ ] Prometheus metrics export
  - [ ] Search latency tracking
  - [ ] Embedding generation metrics
  - [ ] System resource monitoring
- [ ] Add health checks and diagnostics
  - [ ] Deep health checks
  - [ ] Model status monitoring
  - [ ] Index health validation
  - [ ] Database connectivity checks

### **Documentation & Deployment**
- [ ] Complete API documentation
  - [ ] OpenAPI/Swagger documentation
  - [ ] Usage examples and tutorials
  - [ ] Integration guides
  - [ ] Troubleshooting guides
- [ ] Deployment preparation
  - [ ] Docker containerization
  - [ ] Docker Compose setup
  - [ ] Environment configuration
  - [ ] Production deployment guide
- [ ] Performance tuning guide
  - [ ] Hardware recommendations
  - [ ] Configuration optimization
  - [ ] Scaling strategies

### **Quality Assurance**
- [ ] Comprehensive testing suite
  - [ ] Unit tests for all components
  - [ ] Integration tests for API endpoints
  - [ ] Performance tests
  - [ ] Load testing
  - [ ] Security testing
- [ ] Evaluation and benchmarking
  - [ ] Search quality evaluation
  - [ ] Embedding quality assessment
  - [ ] Performance benchmarking
  - [ ] Comparison with baseline systems

### **Final Integration & Polish**
- [ ] End-to-end workflow testing
- [ ] User experience optimization
- [ ] Error message improvement
- [ ] Performance fine-tuning
- [ ] Documentation review and updates
- [ ] Production readiness checklist

---

# Success Metrics & Evaluation

## Technical Metrics
- [ ] **Search Latency**: <2 seconds for typical queries
- [ ] **Embedding Generation**: <30 seconds per document
- [ ] **Search Accuracy**: >80% relevant results in top-10
- [ ] **System Uptime**: >99% availability
- [ ] **Memory Usage**: <8GB for typical workloads

## Functional Metrics
- [ ] **Document Processing**: Support PDFs up to 100MB with streaming upload
- [ ] **Upload Performance**: 100MB files upload and process in <150 seconds
- [ ] **Memory Efficiency**: Constant 64KB memory usage during upload
- [ ] **Multimodal Retrieval**: Text queries return relevant images
- [ ] **Grounding Accuracy**: >95% correct page/bbox coordinates
- [ ] **Concurrent Users**: Support 5+ simultaneous 100MB uploads
- [ ] **Index Size**: Handle 1000+ documents efficiently

## User Experience Metrics
- [ ] **Upload Success Rate**: >95% successful document processing
- [ ] **Search Response Time**: <2 seconds end-to-end
- [ ] **Result Relevance**: User satisfaction >4/5 rating
- [ ] **API Reliability**: <1% error rate
- [ ] **Documentation Quality**: Complete setup in <30 minutes

---

# Risk Mitigation Strategies

## Technical Risks
- **Model Loading Failures**: Implement fallback models and graceful degradation
- **Memory Overflow**: Add memory monitoring and automatic cleanup
- **Index Corruption**: Implement backup/restore and index rebuilding
- **Search Performance**: Add caching and query optimization

## Operational Risks
- **High Resource Usage**: Implement resource limits and monitoring
- **Concurrent Access**: Add proper locking and queue management
- **Data Loss**: Implement backup strategies and data validation
- **Security Vulnerabilities**: Regular security audits and updates

## Integration Risks
- **DocEater Compatibility**: Maintain backward compatibility
- **Database Migration**: Implement safe migration procedures
- **API Breaking Changes**: Use versioning and deprecation strategies
- **Third-party Dependencies**: Pin versions and monitor updates
```
