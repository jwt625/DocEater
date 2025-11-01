# RFD-103: Next Steps and Production Roadmap

**Author:** Augment Agent
**Date:** 2025-11-01
**Status:** Active
**Depends on:** RFD-101 (PGVector + Jina CLIP v2), RFD-102 (FastAPI Endpoints)

---

## Executive Summary

DocEater has successfully completed its core infrastructure development with a fully functional FastAPI web service, multimodal embedding system, and comprehensive document processing pipeline. This RFD outlines the next steps to complete the production-ready system and address the identified gaps.

**Current State:**
- ✅ **API Infrastructure**: 9/9 endpoints working correctly
- ✅ **Document Processing**: PDF upload, processing, and storage complete
- ✅ **Embedding Foundation**: PGVector + Jina CLIP v2 implemented
- ⚠️ **Search Integration**: Endpoints return HTTP 501 (awaiting implementation)
- ⚠️ **Role-Based Access**: Authentication works but roles not enforced

---

## Priority 1: Complete Search Functionality (1-2 weeks)

### Issue: Search Endpoints Not Implemented

**Current Status:**
- Search endpoints return HTTP 501 Not Implemented
- Embedding infrastructure exists but not integrated with search
- Users cannot perform multimodal document search

**Required Implementation:**

#### 1.1 Integrate Embedding Service with Search Endpoints
```python
# Update src/doceater/api/routes/search.py
@router.post("/search")
async def search_documents(
    request: SearchRequest,
    current_user: TokenData = Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    # Replace HTTP 501 with actual search logic
    embedding_service = EmbeddingService()
    query_embedding = await embedding_service.generate_text_embedding(request.query)
    results = await db.search_similar_embeddings(query_embedding, request.top_k)
    return SearchResponse(results=results)
```

#### 1.2 Implement Background Embedding Generation
- Hook embedding generation into document processing pipeline
- Generate embeddings for uploaded documents automatically
- Store text and image embeddings in PGVector tables

#### 1.3 Vector Similarity Search Implementation
- Implement cosine similarity search using PGVector
- Support cross-modal search (text query → image results)
- Add result ranking and metadata enrichment

**Success Criteria:**
- [ ] `POST /api/v1/search` returns HTTP 200 with search results
- [ ] `POST /api/v1/search/similar` returns HTTP 200 with similar documents
- [ ] Multimodal search works (text queries return both text and image results)
- [ ] Search performance <2 seconds for typical queries

---

## Priority 2: Fix Role-Based Access Control (3-5 days)

### Issue: API Keys Have Identical Permissions

**Current Status:**
- Environment variables specify roles: `dk_prod_...:doceat_admin`, `dk_read_...:doceat_reader`
- Implementation ignores roles and gives all API keys `["read", "write"]` scopes
- Both admin and reader keys can perform write operations (delete, upload)

**Required Fix:**

#### 2.1 Update Authentication Logic
```python
# Fix src/doceater/api/auth.py lines 160-173
def parse_api_key_role(api_key_entry: str) -> list[str]:
    """Parse API key role and return appropriate scopes."""
    if ":" in api_key_entry:
        key, role = api_key_entry.split(":", 1)
        if role == "doceat_admin":
            return ["read", "write", "admin"]
        elif role == "doceat_reader":
            return ["read"]
        else:
            return ["read"]  # Default to read-only
    return ["read"]  # Default for malformed entries

# Update TokenData creation to use actual role-based scopes
return TokenData(
    user_id=user_id,
    username=user_id,
    scopes=parse_api_key_role(api_key_entry),  # Use role-based scopes
    exp=datetime.now(UTC) + timedelta(hours=24),
    iat=datetime.now(UTC),
)
```

#### 2.2 Test Role Enforcement
- Verify admin keys can upload/delete documents
- Verify reader keys are rejected for write operations
- Update test suite to validate role-based permissions

**Success Criteria:**
- [ ] Admin API keys can perform all operations
- [ ] Reader API keys can only perform read operations
- [ ] Reader keys receive HTTP 403 for write operations
- [ ] All existing tests pass with role enforcement

---

## Priority 3: Fix Test Suite Authentication Issues (1-2 days)

### Issue: Test Suite Uses Wrong Authentication Headers

**Current Status:**
- 2 out of 48 API tests failing
- Tests use `Authorization: Bearer` header but implementation expects `X-API-Key`
- Root cause: Test configuration mismatch

**Required Fix:**

#### 3.1 Update Test Configuration
```python
# Fix tests/api/conftest.py
@pytest.fixture
def test_client_with_api_key():
    """Test client configured with API key authentication."""
    return TestClient(
        app,
        headers={"X-API-Key": "test-api-key"}  # Use X-API-Key instead of Authorization
    )
```

#### 3.2 Update Failing Tests
- `test_api_key_authentication_success`
- `test_upload_with_api_key_authentication`

**Success Criteria:**
- [ ] All 48 API tests pass
- [ ] Test suite uses correct authentication headers
- [ ] Both JWT and API key authentication tested properly

---

## Priority 4: Production Deployment Preparation (1 week)

### 4.1 Performance Optimization
- [ ] Database query optimization for search endpoints
- [ ] Connection pooling tuning for concurrent requests
- [ ] Caching strategy for frequently accessed embeddings
- [ ] Memory usage optimization for large file uploads

### 4.2 Monitoring and Observability
- [ ] Metrics collection (request latency, processing time, error rates)
- [ ] Health check enhancements with embedding model status
- [ ] Error tracking and alerting integration
- [ ] Performance monitoring dashboards

### 4.3 Security Hardening
- [ ] Rate limiting implementation
- [ ] Request logging and monitoring
- [ ] Input validation and sanitization
- [ ] Security headers and CORS configuration

### 4.4 Documentation and Deployment
- [ ] Complete API documentation with working search endpoints
- [ ] Create deployment guide with database setup instructions
- [ ] Document environment variable configuration
- [ ] Create production deployment checklist

---

## Timeline and Dependencies

| Priority | Task | Estimated Time | Dependencies |
|----------|------|----------------|--------------|
| **P1** | Search Functionality | 1-2 weeks | RFD-101 embedding service |
| **P2** | Role-Based Access | 3-5 days | None |
| **P3** | Test Suite Fixes | 1-2 days | None |
| **P4** | Production Prep | 1 week | P1, P2, P3 complete |

**Total Timeline: 3-4 weeks**

---

## Success Metrics

### Technical Metrics
- [ ] **Search Latency**: <2 seconds for typical queries
- [ ] **Embedding Generation**: <30 seconds per document
- [ ] **Search Accuracy**: >80% relevant results in top-10
- [ ] **System Uptime**: >99% availability
- [ ] **Test Coverage**: >85% overall coverage

### Functional Metrics
- [ ] **Complete API**: 9/9 endpoints fully functional
- [ ] **Role Enforcement**: Proper access control working
- [ ] **Test Quality**: 100% test pass rate
- [ ] **Multimodal Search**: Text queries return relevant images
- [ ] **Production Ready**: Monitoring and deployment complete

---

## Risk Assessment

### High Priority Risks
1. **Embedding Service Integration Complexity**: Vector search implementation may be more complex than anticipated
2. **Performance at Scale**: Search performance with large document sets unknown
3. **Role-Based Access Breaking Changes**: Authentication changes may affect existing functionality

### Mitigation Strategies
- Start with simple embedding integration and iterate
- Performance testing with realistic document sets
- Comprehensive testing of authentication changes
- Staged deployment with rollback procedures

---

## Conclusion

DocEater is in an excellent position with a solid foundation of implemented infrastructure. The remaining work focuses on completing the search functionality, fixing identified issues, and preparing for production deployment. The estimated 3-4 week timeline will deliver a fully functional, production-ready multimodal document processing and search system.

**Next Immediate Actions:**
1. Begin search endpoint implementation using existing embedding infrastructure
2. Fix role-based access control in authentication system
3. Update test suite to use correct authentication headers
4. Plan production deployment and monitoring strategy
