"""
Wrapper module for backward compatibility.

This module re-exports the main classes and functions from the decomposed modules.
New code should import directly from the specific modules:
- core.api_client.AliceAIAgent
- core.data_processor.DataProcessor  
- analyzer.data_analyzer.DataAnalyzer
- core.config.load_config
"""

# Re-export main classes and functions for backward compatibility
from core.api_client import AliceAIAgent
from core.data_processor import DataProcessor
from analyzer.data_analyzer import DataAnalyzer
from core.config import load_config

__all__ = [
    'AliceAIAgent',
    'DataProcessor',
    'DataAnalyzer',
    'load_config'
]