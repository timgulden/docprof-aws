"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "lambda"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, local, no AWS)")
    config.addinivalue_line("markers", "integration: Integration tests (moderate speed, requires AWS)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (slow, full AWS stack)")


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables."""
    monkeypatch.setenv('DB_CLUSTER_ENDPOINT', 'test-cluster.region.rds.amazonaws.com')
    monkeypatch.setenv('DB_NAME', 'test_db')
    monkeypatch.setenv('DB_MASTER_USERNAME', 'test_user')
    monkeypatch.setenv('SOURCE_BUCKET', 'test-bucket')
    monkeypatch.setenv('DYNAMODB_SESSIONS_TABLE_NAME', 'test-sessions')

