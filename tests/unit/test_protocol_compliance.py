"""
Protocol Compliance Tests
Tests that Protocol implementations have correct interfaces without importing full modules
"""

import pytest
from pathlib import Path
import ast
import inspect


def get_class_methods(file_path: Path, class_name: str):
    """Extract method names from a Python class without importing."""
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
            return methods
    return []


def test_database_client_interface():
    """Test that AWSDatabaseClient implements all DatabaseClient Protocol methods"""
    protocol_file = Path(__file__).parent.parent.parent.parent / "MAExpert" / "src" / "effects" / "ingestion_effects.py"
    impl_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
    
    if not protocol_file.exists():
        pytest.skip("MAExpert codebase not found")
    
    # Extract Protocol methods from MAExpert
    protocol_methods = set()
    with open(protocol_file, 'r') as f:
        content = f.read()
        # Find DatabaseClient Protocol definition
        in_protocol = False
        for line in content.split('\n'):
            if 'class DatabaseClient(Protocol):' in line:
                in_protocol = True
                continue
            if in_protocol:
                if line.strip().startswith('def '):
                    method_name = line.strip().split('(')[0].replace('def ', '').strip()
                    protocol_methods.add(method_name)
                elif line.strip() and not line.strip().startswith(' ') and not line.strip().startswith('#'):
                    break
    
    # Extract implementation methods
    impl_methods = set(get_class_methods(impl_file, 'AWSDatabaseClient'))
    
    # Check all Protocol methods are implemented
    missing = protocol_methods - impl_methods
    assert not missing, f"Missing methods in AWSDatabaseClient: {missing}"


def test_pdf_extractor_interface():
    """Test that AWSPDFExtractor implements all PDFExtractor Protocol methods"""
    protocol_file = Path(__file__).parent.parent.parent.parent / "MAExpert" / "src" / "effects" / "ingestion_effects.py"
    impl_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
    
    if not protocol_file.exists():
        pytest.skip("MAExpert codebase not found")
    
    # Extract Protocol methods
    protocol_methods = {'load_pdf', 'extract_text', 'extract_figures'}
    
    # Extract implementation methods
    impl_methods = set(get_class_methods(impl_file, 'AWSPDFExtractor'))
    
    missing = protocol_methods - impl_methods
    assert not missing, f"Missing methods in AWSPDFExtractor: {missing}"


def test_embedding_client_interface():
    """Test that AWSEmbeddingClient implements EmbeddingClient Protocol"""
    impl_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
    
    # EmbeddingClient Protocol requires embed_texts method
    protocol_methods = {'embed_texts'}
    
    impl_methods = set(get_class_methods(impl_file, 'AWSEmbeddingClient'))
    
    missing = protocol_methods - impl_methods
    assert not missing, f"Missing methods in AWSEmbeddingClient: {missing}"


def test_figure_client_interface():
    """Test that AWSFigureDescriptionClient implements FigureDescriptionClient Protocol"""
    impl_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
    
    # FigureDescriptionClient Protocol requires describe_figure method
    protocol_methods = {'describe_figure'}
    
    impl_methods = set(get_class_methods(impl_file, 'AWSFigureDescriptionClient'))
    
    missing = protocol_methods - impl_methods
    assert not missing, f"Missing methods in AWSFigureDescriptionClient: {missing}"


def test_effects_adapter_signatures():
    """Test that effects adapter provides expected functions"""
    adapter_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "effects_adapter.py"
    
    if not adapter_file.exists():
        pytest.skip("Effects adapter file not found")
    
    # Read file and check for expected functions
    with open(adapter_file, 'r') as f:
        content = f.read()
    
    # Check that create_effects_adapter exists
    assert 'def create_effects_adapter' in content, "create_effects_adapter function not found"
    
    # Check that it returns expected keys
    expected_keys = [
        'insert_chunks',
        'insert_book',
        'search_chunks',
        'call_llm',
        'generate_embedding',
        'generate_embeddings_batch',
        'describe_figure'
    ]
    
    for key in expected_keys:
        assert f"'{key}':" in content or f'"{key}":' in content, f"Expected key '{key}' not found in adapter"


def test_lambda_handler_structure():
    """Test that document processor handler has correct structure"""
    handler_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "document_processor" / "handler.py"
    
    if not handler_file.exists():
        pytest.skip("Handler file not found")
    
    with open(handler_file, 'r') as f:
        content = f.read()
    
    # Check for lambda_handler function
    assert 'def lambda_handler' in content, "lambda_handler function not found"
    
    # Check that it uses MAExpert pipeline
    assert 'run_ingestion_pipeline' in content, "Should use MAExpert run_ingestion_pipeline"
    
    # Check for Protocol implementations
    assert 'AWSDatabaseClient' in content, "Should use AWSDatabaseClient"
    assert 'AWSPDFExtractor' in content, "Should use AWSPDFExtractor"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

