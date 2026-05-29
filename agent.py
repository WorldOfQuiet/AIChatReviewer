"""
Wrapper module for backward compatibility.

This module re-exports the main classes and functions from the decomposed modules.
New code should import directly from the specific modules.
"""

# Re-export main classes and functions for backward compatibility
from core.api_client import LLMClient
from core.data_processor import DataProcessor
from analyzer.data_analyzer import DataAnalyzer
from core.config import load_config

__all__ = [
    'LLMClient',
    'DataProcessor',
    'DataAnalyzer',
    'load_config'
]