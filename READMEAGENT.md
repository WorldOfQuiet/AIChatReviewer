# AIChatReviewer - Agent Module Documentation

## Overview

This project analyzes chat conversations using a multi-step LLM-based approach. The system processes chat data, identifies problems/complaints, groups them thematically, and maps results back to original participants.

## Module Structure (After Reorganization)

### Directory Structure

```
AIChatReviewer/
├── core/                     # Core application modules
│   ├── api_client.py        # AliceAIAgent class for API communication
│   ├── data_processor.py    # DataProcessor class for data processing utilities
│   └── config.py            # load_config() function for configuration management
├── utils/                   # Utility scripts
│   └── votes_counter.py     # Vote counting utility
├── visualization/           # Visualization module
│   └── visualizer.py        # Visualizer class for data visualization
├── analyzer/                # Analysis logic directory
│   ├── __init__.py          # Module exports
│   ├── base_analyzer.py     # Common analyzer utilities
│   ├── data_analyzer.py     # Main analyzer orchestrator
│   ├── step1_analyzer.py    # Step 1 - Chat analysis
│   ├── step2_aggregator.py  # Step 2 - Result aggregation
│   └── step3_mapper.py      # Step 3 - Backward mapping
├── agent.py                 # Backward compatibility wrapper (stays in root)
├── main.py                  # Main entry point
├── votes_14-days-n.png      # Example visualization output
├── votes_14-days-R&S.png    # Example visualization output
└── config.json              # Configuration file
```

### Core Modules

1. **`core/api_client.py`** - API Communication
   - **Class**: `AliceAIAgent`
   - **Purpose**: Handles communication with Yandex AI Studio API
   - **Responsibilities**:
     - Load API key from JSON file
     - Load system prompts from text files
     - Send conversation text to LLM and retrieve responses
   - **Dependencies**: `requests`, `json`

2. **`core/data_processor.py`** - Data Processing Utilities
   - **Class**: `DataProcessor` (all static methods)
   - **Purpose**: Provides utility functions for data parsing and manipulation
   - **Key Methods**:
     - `parse_date()`: Convert various date formats to datetime
     - `extract_from_response()`: Extract JSON data from LLM responses
     - `load_chats_from_json()`: Load and validate chat data
     - `group_messages_by_reply_chain()`: Group messages by reply chains
   - **Dependencies**: `json`, `re`, `datetime`

3. **`core/config.py`** - Configuration Management
   - **Function**: `load_config()`
   - **Purpose**: Load and validate configuration from JSON file
   - **Dependencies**: `json`

### Analysis Modules (`analyzer/` directory)

4. **`analyzer/`** - Analysis Logic Directory
   - **`__init__.py`**: Module exports
   - **`base_analyzer.py`**: Common analyzer utilities
     - `_log()`, `_get_int()`, `_get_str()` methods
     - Configuration validation helpers
   - **`step1_analyzer.py`**: Step 1 - Chat Analysis
     - Processes individual chats and message packets
     - Anonymizes authors, sends to LLM for problem identification
   - **`step2_aggregator.py`**: Step 2 - Result Aggregation
     - Aggregates problems from step 1 into thematic groups
     - Uses recursive aggregation with chunking
   - **`step3_mapper.py`**: Step 3 - Backward Mapping
     - Maps grouped problems back to original participants
     - Reconstructs participant information from source chats
   - **`data_analyzer.py`**: Main Analyzer Orchestrator
     - `DataAnalyzer` class that coordinates all three steps
     - Manages configuration, logging, and execution flow

### Utility Modules

5. **`utils/votes_counter.py`** - Vote Counting Utility
   - **Functions**: `count_votes_step1()`, `count_votes_step2()`, `count_votes_step3()`
   - **Purpose**: Count votes/messages across analysis steps
   - **Dependencies**: `json`, `os`, `sys`

6. **`visualization/visualizer.py`** - Visualization Module
   - **Class**: `Visualizer`
   - **Purpose**: Creates visualizations of analysis results
   - **Key Features**:
     - Plot votes over time intervals
     - Apply smoothing and threshold filters
     - Save visualizations as PNG files
   - **Dependencies**: `matplotlib`, `json`, `datetime`

7. **`agent.py`** - Backward Compatibility Wrapper
   - **Purpose**: Maintains original import interface
   - **Implementation**: Imports and re-exports all public classes/functions from new locations
   - **Note**: This is a thin wrapper; new code should import directly from specific modules

### Data Flow

1. **Input**: Chat JSON files (`agent_data/chats.json`)
2. **Step 1**: Chat → Message packets → LLM analysis → Problem identification
3. **Step 2**: Problems → Recursive aggregation → Thematic groups
4. **Step 3**: Groups → Backward mapping → Participants + statistics
5. **Output**: JSON files in `agent_data/` directory

### Configuration

Configuration is managed via `config.json` with sections:
- `shared`: Common settings (logging level, chats file)
- `analyzer`: Analysis parameters (API keys, limits, enabled steps)
- `parser`: VK parser settings (if enabled)
- `visualizer`: Visualization settings

### File Dependencies

- **Input Files**:
  - `api_key.json`: Yandex AI Studio API credentials
  - `agent_data/prompt_for_analysis_step_1*.txt`: Step 1 system prompt
  - `agent_data/prompt_for_analysis_step_2*.txt`: Step 2 system prompt
  - `agent_data/chats.json`: Source chat data

- **Output Files**:
  - `agent_data/analysis_step_1.json`: Step 1 results
  - `agent_data/analysis_step_2.json`: Step 2 results  
  - `agent_data/analysis_step_3.json`: Step 3 results

### Usage

```python
# Original way (via wrapper - maintained for compatibility)
from agent import DataAnalyzer, DataProcessor, AliceAIAgent

# Recommended way (direct imports from new locations)
from core.api_client import AliceAIAgent
from core.data_processor import DataProcessor
from analyzer.data_analyzer import DataAnalyzer
from core.config import load_config

# Visualization imports
from visualization.visualizer import Visualizer

# Utility imports  
from utils.votes_counter import count_votes_step1, count_votes_step2, count_votes_step3
```

### Maintenance Notes

- The project has been reorganized with files moved to logical directories:
  - Core modules (`api_client.py`, `data_processor.py`, `config.py`) → `core/`
  - Utility scripts (`votes_counter.py`) → `utils/`
  - Visualization module (`visualizer.py`) → `visualization/`
  - Analyzer modules remain in `analyzer/`
  - Backward compatibility wrapper (`agent.py`) stays in root
- The modular structure allows independent testing and development of components
- New analysis steps can be added as separate modules in the `analyzer/` directory
- Configuration changes should be reflected in both `config.json` and `config.py` validation
- The `agent.py` wrapper ensures backward compatibility but may be deprecated in future versions
