"""FastAPI Application for DOCX Document Processing.

This module provides a REST API for processing DOCX files and extracting their content
with AI-powered enrichment using Azure OpenAI services.

Endpoints:
    GET /health: Health check endpoint
    POST /process: Process a DOCX file and extract content

The API accepts DOCX files, extracts text, tables, and images, and enriches them
with AI-generated captions, summaries, and markdown content.

Environment Variables:
    See .env.example for required Azure OpenAI configuration.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from .document_processor import process_docx_bytes

load_dotenv()

app = FastAPI(
    title="Docx Vector Prep API",
    description="API for processing DOCX files with AI-powered content enrichment",
    version="0.0.1"
)

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health",
         tags=["Health"],
         summary="Health Check",
         description="Check the health status of the document processing service.")
def health():
    """Health check endpoint.
    
    Returns:
        dict: Status object indicating service health
        
    Example:
        GET /health
        Response: {"status": "ok"}
    """
    return {"status": "ok"}


@app.post("/process",
          tags=["Document Processing"],
          summary="Process DOCX File",
          description="Process a DOCX file and extract enriched content using Azure OpenAI."
          )
async def process_docx(file: UploadFile = File(...)):
    """Process a DOCX file and extract enriched content.
    
    This endpoint accepts a DOCX file, extracts all text, tables, and images,
    and enriches them using Azure OpenAI:
    - Paragraphs: Organized with header hierarchy
    - Tables: Converted to markdown format
    - Images: OCR extraction and caption generation
    
    Args:
        file: DOCX file upload (multipart/form-data)
        
    Returns:
        dict: Processed document data including:
            - document: Metadata (filename, counts, timestamp)
            - content: Raw extracted content (paragraphs, tables, images)
            - chunks: Semantic chunks with header context
            - vector_records: Ready-to-embed records for vector DB
            
    Raises:
        HTTPException 400: If file is not DOCX or is empty
        
    Example:
        POST /process
        Content-Type: multipart/form-data
        file: document.docx
        
        Response: {
            "document": {...},
            "content": {...},
            "chunks": [...],
            "vector_records": [...]
        }
    """
    # Validate file type
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    # Read file content
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # Process the document
    result = process_docx_bytes(data, filename=file.filename)
    return result
