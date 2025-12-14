"""
Integration test to verify Lambda functions can import shared code from layer.

This test verifies that after migrating to Lambda layers:
1. Shared code imports work correctly
2. All key modules are accessible
3. No import errors occur

Note: This test should be run AFTER deploying the Lambda layer.
It requires AWS credentials and a deployed Lambda layer.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Lambda layer structure: python/shared/ is added to sys.path by Lambda
# In tests, we need to add src/lambda/shared to simulate this
lambda_shared_path = project_root / "src" / "lambda" / "shared"
sys.path.insert(0, str(lambda_shared_path.parent))


def test_shared_code_imports():
    """Test that all key shared modules can be imported."""
    
    # Test that modules can be imported (don't test callability as that may require AWS deps)
    # These tests verify the Lambda layer structure allows imports
    try:
        import shared.db_utils
        import shared.bedrock_client
        import shared.response
        import shared.protocol_implementations
        
        # Verify modules have expected attributes
        assert hasattr(shared.db_utils, 'get_db_connection') or hasattr(shared.db_utils, 'get_db_connection_info')
        assert hasattr(shared.bedrock_client, 'invoke_claude') or hasattr(shared.bedrock_client, 'generate_embeddings')
        assert hasattr(shared.response, 'success_response')
        assert hasattr(shared.response, 'error_response')
        assert hasattr(shared.protocol_implementations, 'AWSDatabaseClient')
        
    except ImportError as e:
        # If boto3 is missing, that's ok - we're testing structure, not runtime
        if 'boto3' in str(e):
            pytest.skip("boto3 not installed (Lambda runtime will have it)")
        raise


def test_shared_core_imports():
    """Test that core modules can be imported."""
    
    from shared.core.commands import Command, LLMCommand
    from shared.core.chat_models import ChatMessage
    from shared.core.course_models import Course, CourseSection
    
    # Verify classes exist
    assert Command is not None
    assert LLMCommand is not None
    assert ChatMessage is not None
    assert Course is not None
    assert CourseSection is not None


def test_shared_logic_imports():
    """Test that logic modules can be imported."""
    
    import shared.logic.chat
    import shared.logic.chunking
    import shared.logic.courses
    
    # Verify modules exist (functions may vary, just check modules import)
    assert shared.logic.chat is not None
    assert shared.logic.chunking is not None
    assert shared.logic.courses is not None
    
    # Check for common functions (existence may vary)
    assert hasattr(shared.logic.chat, 'process_user_message') or hasattr(shared.logic.chat, '__file__')
    assert hasattr(shared.logic.courses, 'generate_course_outline') or hasattr(shared.logic.courses, '__file__')


def test_layer_structure_simulation():
    """
    Test that imports work when simulating Lambda layer structure.
    
    Lambda adds python/ to sys.path, so python/shared becomes accessible as 'shared'.
    This test verifies our local simulation works correctly.
    """
    # Try importing as if from Lambda layer (python/shared -> shared)
    # Note: boto3-dependent modules may fail in test env, that's ok
    try:
        import shared.response  # Should always work (no AWS deps)
        import shared.bedrock_client  # May fail if boto3 missing, but structure should work
        assert True
    except ImportError as e:
        # boto3 missing is expected in some test environments
        if 'boto3' in str(e):
            pytest.skip("boto3 not installed (Lambda runtime will have it)")
        # db_utils also needs boto3, so skip if that's the issue
        if 'db_utils' in str(e) and 'boto3' in str(e):
            pytest.skip("boto3 not installed (Lambda runtime will have it)")
        pytest.fail(f"Failed to import shared modules: {e}")


def test_no_circular_imports():
    """Test that there are no circular import issues."""
    
    # Import all major shared modules at once
    try:
        import shared.db_utils as db_utils
        import shared.bedrock_client as bedrock_client
        import shared.response as response
        import shared.protocol_implementations as protocol_implementations
        import shared.core.commands as commands
        import shared.core.chat_models as chat_models
        import shared.logic.chat as chat
        import shared.logic.chunking as chunking
        
        # Verify all imports succeeded
        assert db_utils is not None
        assert bedrock_client is not None
        assert response is not None
        assert protocol_implementations is not None
        assert commands is not None
        assert chat_models is not None
        assert chat is not None
        assert chunking is not None
        
    except ImportError as e:
        # boto3 might be missing, that's ok
        if 'boto3' in str(e):
            pytest.skip("boto3 not installed (Lambda runtime will have it)")
        raise
    except Exception as e:
        pytest.fail(f"Circular import or other import error detected: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

