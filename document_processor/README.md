# 📄 Document Processor for Vector Databases

A powerful document processing pipeline that transforms `.docx` files into vector-ready chunks with intelligent semantic organization. Built for RAG (Retrieval Augmented Generation) applications and vector database ingestion.

## ✨ Features

### 🎯 Intelligent Content Extraction
- **Hierarchical Document Structure** - Preserves heading hierarchy (H1, H2, H3...) for contextual semantic search
- **Multi-Modal Processing** - Extracts text, tables, and images with full metadata
- **Section-Based Chunking** - Groups content under headers for better semantic understanding
- **Header Context Embedding** - Each chunk includes its position in the document hierarchy

### 🤖 AI-Powered Enrichment (Optional)
- **Image OCR & Analysis** - Extracts text and structures from images using Azure OpenAI Vision
- **Markdown Conversion** - Transforms charts, diagrams, and tables in images to markdown
- **Image Captions** - Generates searchable descriptions for visual content
- **Smart Configuration** - Works with or without AI enrichment enabled

### 🚀 Vector Database Ready
- **Optimized for Milvus** - Direct upsert-ready JSON format
- **Rich Metadata** - Each chunk includes type, hierarchy, and contextual information
- **Flexible Chunking** - Both section-level and paragraph-level granularity
- **Clean Output** - No base64 bloat in responses

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Frontend  │ ───► │  FastAPI     │ ───► │  Azure OpenAI   │
│  React + UI │      │   Backend    │      │   (Optional)    │
└─────────────┘      └──────────────┘      └─────────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Vector DB   │
                     │   (Milvus)   │
                     └──────────────┘
```

### Tech Stack

**Backend:**
- FastAPI - High-performance API framework
- python-docx - DOCX parsing
- Pillow - Image processing
- httpx - Azure OpenAI integration

**Frontend:**
- React 18 - Modern UI framework
- Vite - Lightning-fast build tool
- Tailwind CSS - Utility-first styling

## 📦 Installation

### Prerequisites
- Python 3.12+
- Node.js 18+
- Virtual environment (recommended)

### Backend Setup

1. **Activate virtual environment and install dependencies:**

```bash
source /Users/paragjain/dev-works/myenv/bin/activate
cd backend
pip install -r requirements.txt
```

2. **Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# AI Enrichment (Optional)
ENABLE_AI_ENRICHMENT=true

# Azure OpenAI Configuration (if AI enrichment enabled)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

3. **Run the API server:**

```bash
cd backend
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`

### Frontend Setup

1. **Install dependencies:**

```bash
cd frontend
npm install
```

2. **Configure environment (if needed):**

```bash
cp .env.example .env
```

3. **Start development server:**

```bash
npm run dev
```

UI will be available at `http://localhost:5173`

## 🔌 API Reference

### Process Document
```http
POST /process
Content-Type: multipart/form-data

Body:
  file: <docx-file>
```

**Response Structure:**
```json
{
  "document": {
    "filename": "example.docx",
    "processed_at": "2026-02-03T12:34:56Z",
    "paragraph_count": 45,
    "table_count": 3,
    "image_count": 2
  },
  "content": {
    "paragraphs": [...],
    "tables": [...],
    "images": [...]
  },
  "chunks": [
    {
      "id": "section_1",
      "type": "section",
      "text": "Combined content...",
      "metadata": {
        "header_path": ["Chapter 1", "Introduction"],
        "header_context": "Chapter 1 > Introduction",
        "paragraph_count": 5
      },
      "embedding_text": "Chapter 1 > Introduction\n\nContent..."
    }
  ],
  "vector_records": [...]
}
```

### Health Check
```http
GET /health
```

**Response:**
```json
{"status": "ok"}
```

## 📊 Output Structure

The processor generates three types of chunks optimized for semantic search:

### 1. Section Chunks
Combine all paragraphs under a header with full hierarchy context:
```json
{
  "id": "section_1",
  "type": "section",
  "embedding_text": "Introduction > Background\n\nFull section content...",
  "metadata": {
    "header_path": ["Introduction", "Background"],
    "header_context": "Introduction > Background"
  }
}
```

### 2. Paragraph Chunks
Individual paragraphs with header context:
```json
{
  "id": "p_15",
  "type": "paragraph",
  "embedding_text": "Chapter 2 > Methods\n\nParagraph content...",
  "metadata": {
    "header_path": ["Chapter 2", "Methods"],
    "parent_header": "Methods"
  }
}
```

### 3. Table & Image Chunks
Structured data with rich metadata:
```json
{
  "id": "t_1",
  "type": "table",
  "embedding_text": "| Header 1 | Header 2 |\n|----------|----------|\n...",
  "metadata": {
    "row_count": 10,
    "col_count": 3
  }
}
```

## 🎨 Features Showcase

### Hierarchical Context Preservation
Documents maintain their structure through heading hierarchy:
- **Heading 1** → Top-level sections
- **Heading 2** → Subsections  
- **Heading 3** → Sub-subsections

Each chunk knows its position: `"Sales Report > Q4 Results > Regional Performance"`

### Smart Chunking Strategy
- **Section-level**: For broad context queries
- **Paragraph-level**: For precise information retrieval
- **Both included**: Maximum search flexibility

### AI Vision Integration (Optional)
When enabled, the system uses Azure OpenAI to:
- Extract text from images (OCR)
- Convert charts/diagrams to markdown descriptions
- Generate searchable captions
- Analyze visual content structure

## 🔧 Configuration Options

### Disable AI Enrichment
Set `ENABLE_AI_ENRICHMENT=false` to run without Azure OpenAI:
- No image captions (empty strings)
- No image markdown extraction
- Tables use raw markdown only
- Faster processing, lower costs

### Enable AI Enrichment
Set `ENABLE_AI_ENRICHMENT=true` and configure Azure OpenAI:
- Full image analysis with OCR
- Intelligent caption generation
- Visual content to markdown conversion
- Enhanced searchability

## 🚀 Production Deployment

### Docker (Coming Soon)
```bash
docker-compose up
```

### Environment Variables
Ensure these are set in production:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `ENABLE_AI_ENRICHMENT`

## 📝 Use Cases

- **RAG Applications** - Prepare documents for retrieval-augmented generation
- **Semantic Search** - Build searchable document repositories  
- **Knowledge Bases** - Structure enterprise documentation
- **Document Analysis** - Extract and analyze multi-modal content
- **Vector Database Ingestion** - Direct pipeline to Milvus/Qdrant/Pinecone

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - feel free to use this project for commercial or personal purposes.

## 🔗 Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Milvus Vector Database](https://milvus.io/)
- [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

---

**Built with ❤️ for the community**
