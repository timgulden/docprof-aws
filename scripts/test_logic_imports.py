#!/usr/bin/env python3
"""
Test script to validate logic extraction and imports.

Tests that:
1. Core models can be imported
2. Logic functions can be imported
3. Functions work correctly
4. Model adapters work

Run from project root: python3 scripts/test_logic_imports.py
"""

import sys
import os

# Add Lambda source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda'))

def test_core_imports():
    """Test core model imports."""
    print("Testing core imports...")
    try:
        # Import directly to avoid shared/__init__.py which imports AWS deps
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chat_models",
            os.path.join(os.path.dirname(__file__), '..', 'src', 'lambda', 'shared', 'core', 'chat_models.py')
        )
        chat_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chat_models)
        
        ChatMessage = chat_models.ChatMessage
        ChatState = chat_models.ChatState
        SourceCitation = chat_models.SourceCitation
        
        print("  ✓ Core models imported")
        return True
    except Exception as e:
        print(f"  ✗ Core models import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prompt_system():
    """Test prompt system."""
    print("Testing prompt system...")
    try:
        # Import directly to avoid shared/__init__.py
        import importlib
        prompts_module = importlib.import_module('shared.core.prompts')
        get_prompt = prompts_module.get_prompt
        
        # Test system prompt
        system_prompt = get_prompt('chat.system')
        assert len(system_prompt) > 0, "System prompt should not be empty"
        print(f"  ✓ System prompt retrieved ({len(system_prompt)} chars)")
        
        # Test synthesis prompt template
        synthesis_prompt = get_prompt('chat.synthesis', variables={
            'context_section': '',
            'chunks_text': 'Test chunk',
            'history_text': '',
            'user_message': 'Test message'
        })
        assert len(synthesis_prompt) > 0, "Synthesis prompt should not be empty"
        print(f"  ✓ Synthesis prompt template works ({len(synthesis_prompt)} chars)")
        
        return True
    except Exception as e:
        print(f"  ✗ Prompt system failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_logic_functions():
    """Test logic function imports and basic functionality."""
    print("Testing logic functions...")
    try:
        from shared.logic.chat import expand_query_for_retrieval, build_synthesis_prompt
        from shared.core.chat_models import ChatMessage
        
        # Test expand_query_for_retrieval
        expanded = expand_query_for_retrieval('test query')
        assert isinstance(expanded, str), "expanded should be string"
        assert len(expanded) > 0, "expanded query should not be empty"
        print(f"  ✓ expand_query_for_retrieval works: \"{expanded}\"")
        
        # Test build_synthesis_prompt
        chunks = [{'content': 'Test chunk', 'chapter_title': 'Test Chapter', 'page_start': 1, 'page_end': 1}]
        messages = [ChatMessage(role='user', content='Hello')]
        prompt = build_synthesis_prompt(
            user_message='test message',
            conversation_history=messages,
            chunks=chunks
        )
        assert isinstance(prompt, str), "prompt should be string"
        assert len(prompt) > 0, "prompt should not be empty"
        assert 'test message' in prompt, "prompt should contain user message"
        print(f"  ✓ build_synthesis_prompt works ({len(prompt)} chars)")
        
        return True
    except Exception as e:
        print(f"  ✗ Logic functions failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_adapters():
    """Test model adapter functions."""
    print("Testing model adapters...")
    try:
        # Import directly to avoid shared/__init__.py
        import importlib
        adapters = importlib.import_module('shared.model_adapters')
        dict_to_chat_message = adapters.dict_to_chat_message
        chat_message_to_dict = adapters.chat_message_to_dict
        get_expand_query = adapters.get_expand_query
        get_build_prompt = adapters.get_build_prompt
        get_system_prompt = adapters.get_system_prompt
        
        # Test adapter functions return callables
        expand_fn = get_expand_query()
        assert callable(expand_fn), "get_expand_query should return callable"
        
        build_fn = get_build_prompt()
        assert callable(build_fn), "get_build_prompt should return callable"
        
        system_prompt = get_system_prompt()
        assert isinstance(system_prompt, str), "get_system_prompt should return string"
        assert len(system_prompt) > 0, "System prompt should not be empty"
        
        print("  ✓ Adapter functions work")
        
        # Test dict conversion
        msg_dict = {
            'id': 'test-id',
            'role': 'user',
            'content': 'Test message',
            'timestamp': '2025-01-01T00:00:00Z'
        }
        msg = dict_to_chat_message(msg_dict)
        assert msg.role == 'user', "Message role should be 'user'"
        assert msg.content == 'Test message', "Message content should match"
        
        # Convert back
        converted_dict = chat_message_to_dict(msg)
        assert converted_dict['role'] == 'user', "Converted dict should match"
        
        print("  ✓ Dict conversion works")
        
        return True
    except Exception as e:
        print(f"  ✗ Model adapters failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Logic Extraction and Imports")
    print("=" * 60)
    print()
    
    results = []
    results.append(("Core Imports", test_core_imports()))
    results.append(("Prompt System", test_prompt_system()))
    results.append(("Logic Functions", test_logic_functions()))
    results.append(("Model Adapters", test_model_adapters()))
    
    print()
    print("=" * 60)
    print("Test Results")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ All tests passed! Logic extraction successful.")
        print("✅ Code is ready for Lambda packaging.")
        return 0
    else:
        print("❌ Some tests failed. Please fix issues before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
