"""
Integration tests for Lambda function imports.

These tests verify that:
1. Lambda functions can be packaged correctly
2. Imports work in Lambda runtime
3. Functions can start without errors

Requires AWS infrastructure to be deployed.
"""

import pytest
import boto3
import json
import time
from datetime import datetime, timedelta

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def lambda_client():
    """AWS Lambda client."""
    return boto3.client('lambda')


@pytest.fixture(scope="module")
def logs_client():
    """CloudWatch Logs client."""
    return boto3.client('logs')


class TestChatHandlerImports:
    """Test chat handler Lambda imports."""
    
    @pytest.fixture
    def function_name(self):
        """Chat handler function name."""
        return "docprof-dev-chat-handler"
    
    def test_lambda_can_invoke(self, lambda_client, function_name):
        """Test that Lambda function can be invoked."""
        payload = {
            "body": json.dumps({
                "message": "test message",
                "session_id": f"test-{int(time.time())}"
            }),
            "httpMethod": "POST",
            "path": "/chat"
        }
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps(payload)
        )
        
        assert response['StatusCode'] == 200
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        # Should not have import errors
        assert 'errorMessage' not in response_payload or \
               'ImportError' not in str(response_payload.get('errorMessage', '')) and \
               'ModuleNotFoundError' not in str(response_payload.get('errorMessage', ''))
    
    def test_no_import_errors_in_logs(self, logs_client, function_name):
        """Test that no import errors appear in CloudWatch logs."""
        log_group = f"/aws/lambda/{function_name}"
        
        # Get logs from last 5 minutes
        end_time = int(time.time() * 1000)
        start_time = int((time.time() - 300) * 1000)  # 5 minutes ago
        
        # Filter for import errors
        response = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            filterPattern="ImportError ModuleNotFoundError"
        )
        
        # Should have no import errors
        error_events = [e for e in response.get('events', []) 
                       if 'ImportError' in e.get('message', '') or 
                          'ModuleNotFoundError' in e.get('message', '')]
        
        assert len(error_events) == 0, \
            f"Found import errors in logs: {[e['message'] for e in error_events]}"
    
    def test_lambda_package_structure(self, lambda_client, function_name):
        """Test that Lambda package includes shared/ directory."""
        # Get function code location
        response = lambda_client.get_function(FunctionName=function_name)
        code_location = response['Code']['Location']
        
        # Download and check package structure
        import urllib.request
        import zipfile
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            urllib.request.urlretrieve(code_location, tmp_file.name)
            
            with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                # Check for shared/ directory
                shared_files = [f for f in file_list if f.startswith('shared/')]
                assert len(shared_files) > 0, "shared/ directory not found in Lambda package"
                
                # Check for key files
                assert any('shared/logic/chat.py' in f for f in file_list), \
                    "shared/logic/chat.py not found"
                assert any('shared/core/chat_models.py' in f for f in file_list), \
                    "shared/core/chat_models.py not found"
                assert any('shared/core/prompts' in f for f in file_list), \
                    "shared/core/prompts not found"


class TestLambdaLayer:
    """Test Lambda layer contains dependencies."""
    
    @pytest.fixture
    def layer_name(self):
        """Lambda layer name."""
        return "docprof-dev-lambda-layer"
    
    def test_layer_exists(self, lambda_client, layer_name):
        """Test that Lambda layer exists."""
        # List layers (layers are versioned)
        response = lambda_client.list_layers()
        
        layers = [l for l in response.get('Layers', []) 
                 if layer_name in l.get('LayerName', '')]
        
        assert len(layers) > 0, f"Layer {layer_name} not found"
    
    def test_layer_contains_dependencies(self, lambda_client, layer_name):
        """Test that layer contains Python dependencies."""
        # Get layer versions
        response = lambda_client.list_layer_versions(LayerName=layer_name)
        
        if len(response.get('LayerVersions', [])) == 0:
            pytest.skip(f"Layer {layer_name} has no versions")
        
        # Get latest version
        latest_version = response['LayerVersions'][0]
        version = latest_version['Version']
        
        # Get layer details
        layer_response = lambda_client.get_layer_version(
            LayerName=layer_name,
            VersionNumber=version
        )
        
        # Check layer size (should have dependencies)
        code_size = layer_response['Content']['CodeSize']
        assert code_size > 1000000, "Layer seems too small (missing dependencies?)"  # > 1MB
