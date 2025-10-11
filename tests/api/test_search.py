"""Tests for search endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestSearchEndpoints:
    """Test cases for search endpoints."""

    def test_search_documents_not_implemented(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test that search endpoint returns 501 Not Implemented."""
        search_request = {
            "query": "machine learning",
            "top_k": 10,
            "include_images": True,
            "include_text": True,
            "similarity_threshold": 0.1
        }
        
        response = test_client.post(
            "/api/v1/search",
            json=search_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        response_data = response.json()
        assert "embedding service implementation" in response_data["detail"].lower()

    def test_search_documents_unauthenticated(self, test_client: TestClient):
        """Test search endpoint without authentication should fail."""
        search_request = {
            "query": "test query",
            "top_k": 5
        }
        
        response = test_client.post("/api/v1/search", json=search_request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_similar_documents_not_implemented(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test that similar search endpoint returns 501 Not Implemented."""
        similar_request = {
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "top_k": 5,
            "similarity_threshold": 0.2
        }
        
        response = test_client.post(
            "/api/v1/search/similar",
            json=similar_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        response_data = response.json()
        assert "embedding service implementation" in response_data["detail"].lower()

    def test_search_similar_documents_unauthenticated(self, test_client: TestClient):
        """Test similar search endpoint without authentication should fail."""
        similar_request = {
            "document_id": "123e4567-e89b-12d3-a456-426614174000",
            "top_k": 5
        }
        
        response = test_client.post("/api/v1/search/similar", json=similar_request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_documents_invalid_request(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test search endpoint with invalid request data."""
        # Missing required 'query' field
        invalid_request = {
            "top_k": 10
        }
        
        response = test_client.post(
            "/api/v1/search",
            json=invalid_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_similar_documents_invalid_request(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test similar search endpoint with invalid request data."""
        # Missing required 'document_id' field
        invalid_request = {
            "top_k": 5
        }
        
        response = test_client.post(
            "/api/v1/search/similar",
            json=invalid_request,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
