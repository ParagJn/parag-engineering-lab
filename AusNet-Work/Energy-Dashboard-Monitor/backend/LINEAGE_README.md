# Data Lineage Feature - SAP AI Core Integration

## Overview
This module integrates SAP AI Core's Gemini 2.5 Pro model to generate data lineage visualizations for the Energy Dashboard Monitor.

## Components

### 1. SAP AI Client (`sap_ai_client.py`)
A reusable class for interacting with SAP AI Core Orchestration API.

**Features:**
- OAuth 2.0 authentication with token caching
- Gemini 2.5 Pro model integration
- SVG content generation
- Token usage tracking
- Error handling and logging

**Usage:**
```python
from sap_ai_client import SAPAIClient

client = SAPAIClient()
result = client.generate_image_content(prompt="Your prompt here")
svg_content = client.extract_svg_from_response(result)
```

### 2. Test Script (`test_lineage_generation.py`)
Validates the SAP AI Core integration by generating a "Hello World" SVG glyph.

**Features:**
- Generates stylized SVG graphics
- Saves SVG files to `data/lineage-outputs/`
- Optional PNG conversion (requires Cairo library)
- Token usage reporting

## Setup

### Environment Variables
Required variables in `backend/.env`:
```
SAP_CLIENT_ID=<your-client-id>
SAP_CLIENT_SECRET=<your-client-secret>
SAP_TOKEN_URL=<token-endpoint>
SAP_API_URL=<api-endpoint>
SAP_RESOURCE_GROUP=<resource-group>
```

### Dependencies
```bash
pip install requests python-dotenv cairosvg
```

### System Requirements (for PNG conversion)
**macOS:**
```bash
brew install cairo
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libcairo2
```

## Testing

Run the test script:
```bash
cd backend
python test_lineage_generation.py
```

**Expected Output:**
- ✅ Access token generated
- ✅ SVG glyph created
- ✅ File saved to `data/lineage-outputs/hello_world.svg`
- Token usage statistics

## Output Directory
```
data/lineage-outputs/
├── hello_world.svg    # Test output
└── [future lineage diagrams]
```

## Model Details
- **Model:** Gemini 2.5 Pro
- **Provider:** SAP AI Core
- **Capabilities:** SVG generation, data visualization, diagram creation
- **Temperature:** 0.7 (configurable)

## Next Steps
1. ✅ SAP AI Core client class created
2. ✅ Authentication working
3. ✅ SVG generation validated
4. ⏳ PNG conversion (pending Cairo installation)
5. 🔜 Data lineage diagram generation
6. 🔜 Frontend integration
7. 🔜 API endpoint creation

## Token Usage
The test generates approximately:
- Prompt tokens: ~200
- Completion tokens: ~3,000-4,000
- Total: ~3,500-4,500 tokens per request

## Notes
- SVG files are self-contained and can be viewed in any modern browser
- PNG conversion is optional but recommended for better compatibility
- The client caches access tokens to minimize authentication requests
- All outputs are saved to `data/lineage-outputs/` directory