# RFD-104: Multi-GPU Parallelization Strategy

**Author:** Augment Agent
**Date:** 2025-11-03
**Status:** Proposed
**Depends on:** RFD-103 (Production Readiness), Current embedding infrastructure

---

## Executive Summary

**Proposal:** Implement comprehensive multi-GPU parallelization to leverage available hardware resources and dramatically increase DocEater's request handling capacity.

**Current State:**
- **Hardware:** 2x NVIDIA H100 GPUs (80GB HBM3 each = 160GB total)
- **Utilization:** GPU 0: ~5%, GPU 1: 0% (massive underutilization)
- **Bottleneck:** Single GPU model loading, sequential processing, single worker architecture

**Proposed Improvements:**
- **4-6x Request Throughput:** From ~10 to 40-60 requests/minute
- **2-3x Document Processing Speed:** Parallel background processing
- **3-5x Embedding Generation Speed:** Larger batches + dual GPU utilization
- **70%+ GPU Utilization:** Both GPUs actively processing workloads

---

## Current Architecture Analysis

### Hardware Resources
```
GPU 0: NVIDIA H100 80GB HBM3 - 4.7GB used (5% utilization)
GPU 1: NVIDIA H100 80GB HBM3 - 0GB used (0% utilization)
Total Available: 160GB GPU memory, ~95% unused
```

### Current Bottlenecks
1. **Single GPU Usage:** `model.to("cuda")` only targets GPU 0
2. **Global Model Instance:** One shared SentenceTransformer across all requests
3. **Sequential Processing:** Background tasks process documents one at a time
4. **Single Worker Default:** `api_workers=1` configuration
5. **Conservative Batching:** Small batch sizes due to single GPU memory constraints

### Performance Limitations
- **Concurrent Documents:** 1-2 maximum
- **Request Queue:** Serialized processing creates bottlenecks
- **Large Files:** 14MB PDFs take 60-120 seconds
- **Resource Waste:** 97% of available GPU compute unused

---

## Proposed Multi-GPU Architecture

### 1. GPU Pool Management System

```
┌─────────────────────────────────────────────────────────────┐
│                    GPU Pool Manager                        │
├─────────────────────────────────────────────────────────────┤
│  GPU 0: H100 (80GB)     │  GPU 1: H100 (80GB)             │
│  ├─ Model Instance       │  ├─ Model Instance               │
│  ├─ Active Tasks: 3      │  ├─ Active Tasks: 2              │
│  ├─ Memory: 45GB/80GB    │  ├─ Memory: 30GB/80GB           │
│  └─ Load Score: 0.6      │  └─ Load Score: 0.4              │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- **Dynamic Load Balancing:** Assign tasks to least loaded GPU
- **Real-time Monitoring:** Track GPU memory, utilization, temperature
- **Task Affinity:** Maintain task-to-GPU assignments for lifecycle
- **Automatic Failover:** Graceful degradation if GPU becomes unavailable

### 2. Multi-Worker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer                           │
├─────────────────────────────────────────────────────────────┤
│  Worker 1 → GPU 0     │  Worker 2 → GPU 1                 │
│  Worker 3 → GPU 0     │  Worker 4 → GPU 1                 │
└─────────────────────────────────────────────────────────────┘
```

**Configuration:**
- **4-6 Uvicorn Workers:** Optimal for 2 GPUs (2-3 workers per GPU)
- **GPU Affinity:** Workers assigned to specific GPUs via environment variables
- **Per-GPU Models:** Independent Jina CLIP v2 instances per GPU
- **Request Distribution:** Intelligent routing based on GPU availability

### 3. Enhanced Concurrent Processing

```
Current:  Document A → Document B → Document C (Sequential)
Proposed: Document A (GPU 0) ∥ Document B (GPU 1) ∥ Document C (GPU 0)
```

**Improvements:**
- **Parallel Background Tasks:** Multiple documents processed simultaneously
- **GPU-Aware Scheduling:** Distribute embedding tasks across available GPUs
- **Increased Concurrency:** `max_concurrent_files` increased from 3 to 8-12
- **Better Resource Utilization:** Both GPUs actively processing workloads

---

## Implementation Plan

### Phase 1: GPU Pool Management (Week 1)
**Deliverables:**
- `GPUManager` class for device discovery and monitoring
- Real-time GPU memory and utilization tracking
- Load balancing algorithm for optimal GPU selection
- Task assignment and lifecycle management

**Key Components:**
- GPU device enumeration and capability detection
- Memory usage monitoring with nvidia-ml-py integration
- Load scoring algorithm (memory + utilization + active tasks)
- Async task assignment with proper cleanup

### Phase 2: Multi-GPU Embedding Service (Week 1-2)
**Deliverables:**
- `MultiGPUEmbeddingService` with automatic load balancing
- Per-GPU model loading and management
- Enhanced batch processing with larger batch sizes
- GPU-aware error handling and fallback mechanisms

**Key Features:**
- Dynamic GPU selection based on current load
- Optimal batch size calculation per GPU memory availability
- Task-aware embedding generation with proper GPU assignment
- Graceful degradation to single GPU or CPU if needed

### Phase 3: Enhanced Processing Service (Week 2)
**Deliverables:**
- Modified `DocumentProcessingService` for concurrent processing
- GPU-aware background task scheduling
- Increased concurrency limits and better resource management
- Integration with multi-GPU embedding service

**Improvements:**
- Multiple concurrent document processing pipelines
- GPU assignment for embedding generation tasks
- Better error handling for GPU resource exhaustion
- Performance monitoring and metrics collection

### Phase 4: Multi-Worker Configuration (Week 2-3)
**Deliverables:**
- Uvicorn worker configuration with GPU affinity
- Environment variable management for GPU assignment
- Shared model loading strategies across workers
- Load testing and performance validation

**Configuration Changes:**
```bash
DOCEATER_API_WORKERS=4                    # 4 workers for 2 GPUs
DOCEATER_MAX_CONCURRENT_FILES=8           # Increased from 3
DOCEATER_GPU_MEMORY_THRESHOLD=0.8         # 80% memory usage limit
DOCEATER_ENABLE_MULTI_GPU=true            # Enable multi-GPU features
```

### Phase 5: Monitoring & Optimization (Week 3-4)
**Deliverables:**
- GPU utilization monitoring and dashboards
- Performance metrics and throughput tracking
- Auto-scaling batch size adjustment
- Production deployment and validation

---

## Expected Performance Improvements

### Throughput Metrics
| Metric | Current | Proposed | Improvement |
|--------|---------|----------|-------------|
| Concurrent Documents | 1-2 | 6-8 | 4x |
| Request Throughput | ~10/min | 40-60/min | 4-6x |
| Large File Processing | 60-120s | 20-40s | 2-3x |
| GPU 0 Utilization | 5% | 70% | 14x |
| GPU 1 Utilization | 0% | 70% | ∞ |

### Batch Size Optimization
```
Current Batch Sizes (Single GPU):
- Text Embeddings: 1-8 items
- Image Embeddings: 8-16 items

Proposed Batch Sizes (Dual GPU):
- Text Embeddings: 16-64 items
- Image Embeddings: 32-64 items
- Dynamic Sizing: Based on available GPU memory
```

### Resource Utilization
- **GPU Memory:** 80-120GB actively used (vs current 5GB)
- **Processing Parallelism:** 2x GPUs processing simultaneously
- **Worker Efficiency:** 4-6 workers handling concurrent requests
- **Background Tasks:** Multiple documents processed in parallel

---

## Risk Assessment

### Technical Risks
- **Memory Management:** Risk of GPU OOM with larger batches
  - *Mitigation:* Dynamic batch sizing and memory monitoring
- **Model Loading:** Increased startup time with multiple GPU models
  - *Mitigation:* Async model loading and warmup strategies
- **Synchronization:** Race conditions in GPU assignment
  - *Mitigation:* Proper async locks and task lifecycle management

### Operational Risks
- **Complexity:** Increased system complexity and debugging difficulty
  - *Mitigation:* Comprehensive logging and monitoring
- **Fallback:** System behavior if GPUs become unavailable
  - *Mitigation:* Graceful degradation to single GPU or CPU
- **Configuration:** Worker and GPU configuration management
  - *Mitigation:* Environment variable validation and defaults

---

## Success Metrics

### Performance Targets
- **Request Throughput:** 40+ requests/minute sustained
- **GPU Utilization:** 60-80% on both GPUs during peak load
- **Processing Time:** <30 seconds for 10MB+ PDFs
- **Concurrent Users:** Support 20+ simultaneous users

### Monitoring Requirements
- Real-time GPU utilization and memory usage dashboards
- Request throughput and response time metrics
- Background task processing queue depth
- Error rates and fallback mechanism usage

---

## Next Steps

1. **Approval:** Review and approve this RFD
2. **Implementation:** Begin Phase 1 (GPU Pool Management)
3. **Testing:** Validate each phase with performance benchmarks
4. **Deployment:** Gradual rollout with monitoring and validation
5. **Optimization:** Fine-tune based on production metrics

**Estimated Timeline:** 3-4 weeks for full implementation
**Resource Requirements:** Development time only (hardware already available)
**Dependencies:** None (builds on existing infrastructure)
