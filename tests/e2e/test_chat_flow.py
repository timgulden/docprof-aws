"""
End-to-end tests for chat functionality.

These tests verify complete user flows:
1. Create session
2. Send message
3. Get response with citations
4. Continue conversation

Requires full AWS infrastructure and may take several minutes.
"""

import pytest
import boto3
import json
import time
from datetime import datetime

# Mark all tests as E2E tests
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def api_gateway_url():
    """API Gateway base URL."""
    # This should be set via environment variable or pytest config
    # For now, we'll try to get it from Terraform outputs
    import subprocess
    try:
        result = subprocess.run(
            ['terraform', 'output', '-raw', 'api_gateway_url'],
            cwd='terraform/environments/dev',
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    # Fallback: use environment variable or default
    import os
    return os.getenv('API_GATEWAY_URL', 'https://api.example.com')


@pytest.fixture(scope="module")
def http_client():
    """HTTP client for API calls."""
    import requests
    return requests


class TestChatFlow:
    """Test complete chat flow."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.session_id = f"test-session-{int(time.time())}"
        yield
        # Cleanup: delete test session if needed
    
    def test_create_session_and_send_message(self, api_gateway_url, http_client):
        """Test creating a session and sending a message."""
        # Step 1: Send first message (creates session automatically)
        response = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "What is DCF valuation?",
                "session_id": self.session_id
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert 'message' in data or 'content' in data
        assert 'session_id' in data
        assert data['session_id'] == self.session_id
        
        # Step 2: Send follow-up message
        response2 = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "How is it different from other valuation methods?",
                "session_id": self.session_id
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert 'message' in data2 or 'content' in data2
    
    def test_response_contains_citations(self, api_gateway_url, http_client):
        """Test that responses include source citations."""
        response = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "Explain discounted cash flow",
                "session_id": f"test-citations-{int(time.time())}"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for citations in response
        message_content = data.get('message', data.get('content', ''))
        
        # Should have citation markers [1], [2], etc. or sources array
        has_citations = (
            '[' in message_content and ']' in message_content or
            'sources' in data or
            'citations' in data
        )
        
        assert has_citations, "Response should include source citations"
    
    def test_session_persistence(self, api_gateway_url, http_client):
        """Test that session persists across multiple messages."""
        session_id = f"test-persistence-{int(time.time())}"
        
        # Send first message
        response1 = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "What is goodwill?",
                "session_id": session_id
            },
            headers={"Content-Type": "application/json"}
        )
        assert response1.status_code == 200
        
        # Wait a moment
        time.sleep(1)
        
        # Send second message referencing first
        response2 = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "How is it calculated?",
                "session_id": session_id
            },
            headers={"Content-Type": "application/json"}
        )
        assert response2.status_code == 200
        
        # Both should reference same session
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1['session_id'] == session_id
        assert data2['session_id'] == session_id
    
    def test_error_handling(self, api_gateway_url, http_client):
        """Test error handling for invalid requests."""
        # Test with missing message
        response = http_client.post(
            f"{api_gateway_url}/chat",
            json={"session_id": "test-error"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return error (400 or 422)
        assert response.status_code >= 400
        
        # Test with invalid session format
        response2 = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "test",
                "session_id": ""  # Empty session ID
            },
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle gracefully (create new session or return error)
        assert response2.status_code in [200, 400, 422]


class TestChatWithRealData:
    """Test chat with real book data (requires books in Aurora)."""
    
    @pytest.mark.skip(reason="Requires books to be ingested first")
    def test_chat_with_book_content(self, api_gateway_url, http_client):
        """Test chat queries that should find book content."""
        # This test requires books to be in Aurora
        # Query should return citations from books
        
        response = http_client.post(
            f"{api_gateway_url}/chat",
            json={
                "message": "What does the book say about valuation?",
                "session_id": f"test-book-{int(time.time())}"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have sources from books
        assert 'sources' in data or 'citations' in data
        sources = data.get('sources', data.get('citations', []))
        assert len(sources) > 0, "Should have sources from books"
