"""
Unit tests for Protocol implementations
Tests that AWS Protocol implementations match MAExpert interfaces

Note: These tests use AST parsing to verify interface compliance without
requiring full module imports (which would need AWS dependencies).
"""

import pytest
from pathlib import Path
import ast


def get_class_methods(file_path: Path, class_name: str):
    """Extract method names from a Python class without importing."""
    if not file_path.exists():
        return []
    
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


class TestProtocolCompliance:
    """Test that Protocol implementations match MAExpert interfaces"""
    
    @pytest.fixture
    def protocol_file(self):
        """Path to MAExpert Protocol definitions"""
        return Path(__file__).parent.parent.parent.parent / "MAExpert" / "src" / "effects" / "ingestion_effects.py"
    
    @pytest.fixture
    def impl_file(self):
        """Path to our Protocol implementations"""
        return Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
    
    def test_database_client_has_all_methods(self, protocol_file, impl_file):
        """Verify AWSDatabaseClient implements all DatabaseClient Protocol methods"""
        if not protocol_file.exists():
            pytest.skip("MAExpert codebase not found")
        
        # Required methods from DatabaseClient Protocol
        required_methods = {
            'find_book',
            'delete_book_contents',
            'insert_book',
            'update_book_cover',
            'update_book_total_pages',
            'get_book_by_id',
            'update_book_pdf',
            'upsert_chapter_document',
            'insert_figures',
            'insert_chunks',
            'update_ingestion_metrics',
            'get_existing_figure_hashes',
            'get_existing_chunk_hashes',
            'get_ingestion_counts',
            'search_chunks',
            'fetch_chapter_documents'
        }
        
        impl_methods = set(get_class_methods(impl_file, 'AWSDatabaseClient'))
        
        missing = required_methods - impl_methods
        assert not missing, f"Missing methods: {missing}"
    
    def test_pdf_extractor_has_all_methods(self, impl_file):
        """Verify AWSPDFExtractor implements all PDFExtractor Protocol methods"""
        required_methods = {'load_pdf', 'extract_text', 'extract_figures'}
        
        impl_methods = set(get_class_methods(impl_file, 'AWSPDFExtractor'))
        
        missing = required_methods - impl_methods
        assert not missing, f"Missing methods: {missing}"
    
    def test_embedding_client_has_all_methods(self, impl_file):
        """Verify AWSEmbeddingClient implements EmbeddingClient Protocol"""
        required_methods = {'embed_texts'}
        
        impl_methods = set(get_class_methods(impl_file, 'AWSEmbeddingClient'))
        
        missing = required_methods - impl_methods
        assert not missing, f"Missing methods: {missing}"
    
    def test_figure_client_has_all_methods(self, impl_file):
        """Verify AWSFigureDescriptionClient implements FigureDescriptionClient Protocol"""
        required_methods = {'describe_figure'}
        
        impl_methods = set(get_class_methods(impl_file, 'AWSFigureDescriptionClient'))
        
        missing = required_methods - impl_methods
        assert not missing, f"Missing methods: {missing}"


class TestCodeStructure:
    """Test code structure and patterns"""
    
    def test_protocol_implementations_file_exists(self):
        """Verify protocol implementations file exists"""
        impl_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "protocol_implementations.py"
        assert impl_file.exists(), "protocol_implementations.py not found"
    
    def test_effects_adapter_file_exists(self):
        """Verify effects adapter file exists"""
        adapter_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "shared" / "effects_adapter.py"
        assert adapter_file.exists(), "effects_adapter.py not found"
    
    def test_document_processor_handler_exists(self):
        """Verify document processor handler exists"""
        handler_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "document_processor" / "handler.py"
        assert handler_file.exists(), "handler.py not found"
    
    def test_handler_uses_maexpert_pipeline(self):
        """Verify handler uses MAExpert ingestion pipeline"""
        handler_file = Path(__file__).parent.parent.parent / "src" / "lambda" / "document_processor" / "handler.py"
        
        with open(handler_file, 'r') as f:
            content = f.read()
        
        assert 'run_ingestion_pipeline' in content, "Handler should use MAExpert run_ingestion_pipeline"
        assert 'AWSDatabaseClient' in content, "Handler should use AWS Protocol implementations"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
