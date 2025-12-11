"""
Unit tests for effects adapter
Tests that effects adapter structure matches MAExpert signatures
"""

import pytest
from pathlib import Path
import ast


def get_function_names(file_path: Path):
    """Extract function names from a Python file."""
    if not file_path.exists():
        return []
    
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    return functions


def get_dict_keys_from_function(file_path: Path, function_name: str):
    """Extract dictionary keys returned by a function."""
    if not file_path.exists():
        return []
    
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            # Look for return statement with dict
            for item in node.body:
                if isinstance(item, ast.Return):
                    if isinstance(item.value, ast.Dict):
                        keys = []
                        for key in item.value.keys:
                            if isinstance(key, ast.Constant):
                                keys.append(key.value)
                            elif isinstance(key, ast.Str):  # Python < 3.8
                                keys.append(key.s)
                        return keys
    return []


class TestEffectsAdapterStructure:
    """Test effects adapter structure"""
    
    @pytest.fixture
    def adapter_file(self):
        """Path to effects adapter file"""
        return Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "effects_adapter.py"
    
    def test_create_effects_adapter_exists(self, adapter_file):
        """Verify create_effects_adapter function exists"""
        functions = get_function_names(adapter_file)
        assert 'create_effects_adapter' in functions, "create_effects_adapter function not found"
    
    def test_create_command_executor_exists(self, adapter_file):
        """Verify create_command_executor function exists"""
        functions = get_function_names(adapter_file)
        assert 'create_command_executor' in functions, "create_command_executor function not found"
    
    def test_adapter_returns_expected_keys(self, adapter_file):
        """Verify adapter returns expected effect functions"""
        expected_keys = [
            'insert_chunks',
            'insert_book',
            'search_chunks',
            'call_llm',
            'generate_embedding',
            'generate_embeddings_batch',
            'describe_figure',
            'get_db_connection'
        ]
        
        keys = get_dict_keys_from_function(adapter_file, 'create_effects_adapter')
        
        # Check that all expected keys are present
        missing = set(expected_keys) - set(keys)
        assert not missing, f"Missing keys in adapter: {missing}"
    
    def test_adapter_file_structure(self, adapter_file):
        """Verify adapter file has correct structure"""
        assert adapter_file.exists(), "effects_adapter.py not found"
        
        with open(adapter_file, 'r') as f:
            content = f.read()
        
        # Check for key components
        assert 'def create_effects_adapter' in content
        assert 'def create_command_executor' in content
        assert 'insert_chunks' in content
        assert 'call_llm' in content
        assert 'generate_embedding' in content


class TestEffectsAdapterSignatures:
    """Test that adapter functions match expected signatures"""
    
    @pytest.fixture
    def adapter_file(self):
        """Path to effects adapter file"""
        return Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "effects_adapter.py"
    
    def test_insert_chunks_signature(self, adapter_file):
        """Verify insert_chunks function signature"""
        with open(adapter_file, 'r') as f:
            content = f.read()
        
        # Check signature matches MAExpert: insert_chunks(book_id, chunks, embeddings)
        assert 'def insert_chunks(' in content
        assert 'book_id:' in content or 'book_id,' in content
        assert 'chunks:' in content or 'chunks,' in content
        assert 'embeddings:' in content or 'embeddings)' in content
    
    def test_call_llm_signature(self, adapter_file):
        """Verify call_llm function signature"""
        with open(adapter_file, 'r') as f:
            content = f.read()
        
        # Check signature matches MAExpert: call_llm(prompt, temperature)
        assert 'def call_llm(' in content
        assert 'prompt:' in content or 'prompt,' in content
    
    def test_generate_embedding_signature(self, adapter_file):
        """Verify generate_embedding function signature"""
        with open(adapter_file, 'r') as f:
            content = f.read()
        
        # Check signature matches MAExpert: generate_embedding(text)
        assert 'def generate_embedding(' in content
        assert 'text:' in content or 'text)' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
