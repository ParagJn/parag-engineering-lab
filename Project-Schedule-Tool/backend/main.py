"""
FastAPI Backend for Project Schedule Tool

This backend provides AI-powered intelligence to the frontend React application.
It uses the Universal LLM Client to interact with various AI models.

Author: Auto-generated
Date: 2026-07-29
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import json
import os
from pathlib import Path
from datetime import datetime

from llm_client import UniversalLLMClient, LLMClientError

# Initialize FastAPI app
app = FastAPI(
    title="Project Schedule Tool API",
    description="AI-powered backend for project scheduling and planning",
    version="1.0.0"
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProjectScheduleAPI")

# Global LLM client instance
llm_client: Optional[UniversalLLMClient] = None


# Pydantic Models for Request/Response
class LLMRequest(BaseModel):
    """Request model for LLM generation"""
    prompt: str = Field(..., description="The prompt to send to the LLM")
    model: Optional[str] = Field(None, description="Specific model to use (leave empty for default)")
    provider: Optional[str] = Field(None, description="Provider to use (leave empty for default)")
    max_tokens: Optional[int] = Field(25000, description="Maximum tokens to generate")


class LLMResponse(BaseModel):
    """Response model for LLM generation"""
    success: bool
    response: Optional[Dict[Any, Any]] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    timestamp: str


class ModelInfo(BaseModel):
    """Model information"""
    provider: str
    model_name: str
    capabilities: List[str]
    is_default: bool
    max_tokens: Optional[int]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    llm_client_initialized: bool


class TaskAnalysisRequest(BaseModel):
    """Request for task analysis"""
    task_description: str
    context: Optional[Dict[str, Any]] = None


class TaskAnalysisResponse(BaseModel):
    """Response for task analysis"""
    success: bool
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProjectOptimizationRequest(BaseModel):
    """Request for project optimization"""
    project_data: Dict[str, Any]
    optimization_goals: List[str]


class ProjectOptimizationResponse(BaseModel):
    """Response for project optimization"""
    success: bool
    optimizations: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class SoWGenerationRequest(BaseModel):
    """Request for Statement of Work generation"""
    project_name: str
    customer: str
    background: Optional[str] = None
    assumptions: Optional[str] = None
    out_of_scope: Optional[str] = None


class SoWGenerationResponse(BaseModel):
    """Response for Statement of Work generation"""
    success: bool
    sow_content: Optional[str] = None
    needs_more_info: bool = False
    questions: Optional[List[str]] = None
    error: Optional[str] = None
    timestamp: str


# Dependency to get LLM client
def get_llm_client() -> UniversalLLMClient:
    """Dependency to get the LLM client instance"""
    global llm_client
    if llm_client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")
    return llm_client


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global llm_client
    try:
        llm_client = UniversalLLMClient(config_path="config.json")
        logger.info("✅ LLM Client initialized successfully")
        logger.info(f"Available models: {len(llm_client.list_available_models())}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM client: {e}")
        # Don't fail startup, but log the error
        llm_client = None


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down API server")


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        llm_client_initialized=llm_client is not None
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Project Schedule Tool API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# List available models
@app.get("/models", response_model=List[ModelInfo])
async def list_models(client: UniversalLLMClient = Depends(get_llm_client)):
    """List all available AI models"""
    try:
        models = client.list_available_models()
        return [ModelInfo(**model) for model in models]
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get default model
@app.get("/models/default")
async def get_default_model(client: UniversalLLMClient = Depends(get_llm_client)):
    """Get the default model configuration"""
    try:
        provider, model = client.get_default_model()
        return {
            "provider": provider,
            "model": model
        }
    except Exception as e:
        logger.error(f"Error getting default model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Generic LLM generation endpoint
@app.post("/generate", response_model=LLMResponse)
async def generate_text(
    request: LLMRequest,
    client: UniversalLLMClient = Depends(get_llm_client)
):
    """
    Generate text using the LLM.
    
    This is a generic endpoint that can be used for any text generation task.
    """
    # Get model info upfront for error reporting
    provider_name = request.provider if request.provider else client.config['settings']['default_provider']
    model_name = request.model if request.model else client.config['settings']['default_model']
    
    try:
        # Prepare kwargs
        kwargs = {}
        if request.max_tokens:
            kwargs['max_tokens'] = request.max_tokens
        
        # Generate response
        response = client.generate(
            prompt=request.prompt,
            model=request.model if request.model else None,
            provider=request.provider if request.provider else None,
            **kwargs
        )
        
        return LLMResponse(
            success=True,
            response=response,
            model_used=model_name,
            provider_used=provider_name,
            timestamp=datetime.now().isoformat()
        )
        
    except LLMClientError as e:
        logger.error(f"LLM Client error: {e}")
        return LLMResponse(
            success=False,
            error=str(e),
            model_used=model_name,
            provider_used=provider_name,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return LLMResponse(
            success=False,
            error=f"Internal server error: {str(e)}",
            model_used=model_name,
            provider_used=provider_name,
            timestamp=datetime.now().isoformat()
        )


# Task analysis endpoint
@app.post("/analyze/task", response_model=TaskAnalysisResponse)
async def analyze_task(
    request: TaskAnalysisRequest,
    client: UniversalLLMClient = Depends(get_llm_client)
):
    """
    Analyze a task description and provide structured insights.
    
    This endpoint uses AI to break down tasks, estimate effort,
    identify dependencies, and suggest optimal scheduling.
    """
    try:
        # Build analysis prompt
        context_str = ""
        if request.context:
            context_str = f"\n\nContext:\n{request.context}"
        
        prompt = f"""Analyze the following task and provide a structured breakdown:

Task: {request.task_description}{context_str}

Please provide:
1. A refined task title (concise, action-oriented)
2. Estimated effort in person-days (provide a range: min, max, likely)
3. Key dependencies or prerequisites
4. Potential risks or challenges
5. Suggested sub-tasks if the task is complex
6. Priority recommendation (High, Medium, Low) with justification

Format your response as JSON with the following structure:
{{
    "title": "string",
    "effort_estimate": {{"min": number, "max": number, "likely": number}},
    "dependencies": ["string"],
    "risks": ["string"],
    "sub_tasks": ["string"],
    "priority": {{"level": "string", "justification": "string"}}
}}"""
        
        response = client.generate(prompt=prompt)
        
        # Parse the response (this is simplified - you might need more robust parsing)
        return TaskAnalysisResponse(
            success=True,
            analysis=response
        )
        
    except Exception as e:
        logger.error(f"Task analysis error: {e}")
        return TaskAnalysisResponse(
            success=False,
            error=str(e)
        )


# Project optimization endpoint
@app.post("/optimize/project", response_model=ProjectOptimizationResponse)
async def optimize_project(
    request: ProjectOptimizationRequest,
    client: UniversalLLMClient = Depends(get_llm_client)
):
    """
    Optimize a project schedule based on given goals.
    
    This endpoint uses AI to suggest optimizations for:
    - Resource allocation
    - Task sequencing
    - Parallel execution opportunities
    - Critical path optimization
    """
    try:
        prompt = f"""Analyze this project and suggest optimizations:

Project Data:
{request.project_data}

Optimization Goals:
{', '.join(request.optimization_goals)}

Provide specific, actionable recommendations for:
1. Resource reallocation opportunities
2. Tasks that can be parallelized
3. Critical path optimizations
4. Risk mitigation strategies
5. Timeline compression opportunities

Format as JSON array of optimization suggestions, each with:
{{
    "category": "string",
    "description": "string",
    "impact": "High|Medium|Low",
    "effort": "Easy|Moderate|Difficult",
    "timeline_savings": "number (in days)"
}}"""
        
        response = client.generate(prompt=prompt, max_tokens=25000)
        
        return ProjectOptimizationResponse(
            success=True,
            optimizations=response
        )
        
    except Exception as e:
        logger.error(f"Project optimization error: {e}")
        return ProjectOptimizationResponse(
            success=False,
            error=str(e)
        )


# Natural language query endpoint
@app.post("/query")
async def natural_language_query(
    query: str,
    context: Optional[Dict[str, Any]] = None,
    client: UniversalLLMClient = Depends(get_llm_client)
):
    """
    Answer natural language queries about project planning.
    
    Examples:
    - "What's the critical path for this project?"
    - "How can I reduce the timeline by 2 weeks?"
    - "What are the risks in the current schedule?"
    """
    try:
        context_str = ""
        if context:
            context_str = f"\n\nProject Context:\n{context}"
        
        prompt = f"""You are an expert project management assistant. Answer the following question:

Question: {query}{context_str}

Provide a clear, concise, and actionable answer based on project management best practices."""
        
        response = client.generate(prompt=prompt)
        
        return {
            "success": True,
            "query": query,
            "answer": response,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Statement of Work generation endpoint
@app.post("/generate/sow", response_model=SoWGenerationResponse)
async def generate_sow(
    request: SoWGenerationRequest,
    client: UniversalLLMClient = Depends(get_llm_client)
):
    """
    Generate a professional Statement of Work (SoW) document.
    
    This endpoint analyzes the provided project information and generates
    a comprehensive SoW document following industry best practices.
    
    The AI will:
    1. Analyze the background, assumptions, and out-of-scope information
    2. Determine if sufficient information is provided
    3. Request additional details if needed
    4. Generate a professional SoW document with proper sections
    """
    try:
        # Check if we have at least background information
        if not request.background or len(request.background.strip()) < 50:
            return SoWGenerationResponse(
                success=False,
                needs_more_info=True,
                questions=[
                    "Please provide detailed project background information (at least a few paragraphs).",
                    "What is the business context and problem this project aims to solve?",
                    "What are the key objectives and expected outcomes?"
                ],
                timestamp=datetime.now().isoformat()
            )
        
        # Build the prompt for SoW generation
        prompt = f"""You are an expert business analyst and technical writer specializing in Statement of Work (SoW) documents.

PROJECT INFORMATION:
- Project Name: {request.project_name}
- Customer: {request.customer}

BACKGROUND:
{request.background}

ASSUMPTIONS:
{request.assumptions if request.assumptions else "Not provided"}

OUT OF SCOPE:
{request.out_of_scope if request.out_of_scope else "Not provided"}

TASK:
First, analyze the provided information to determine if it's sufficient to create a professional SoW document.

If the information is insufficient, respond with a JSON object in this format:
{{
    "sufficient": false,
    "questions": ["question 1", "question 2", ...]
}}

If the information is sufficient, generate a comprehensive Statement of Work document with the following sections:

1. **Background and Context**
   - Provide 2-4 paragraphs explaining the business context, current state, and why this project is needed
   - Use the background information provided to create a compelling narrative

2. **Scope**
   - Create multiple scope sections (e.g., 1.3.1, 1.3.2, etc.) based on the background
   - Each scope section should have:
     * Scope Overview (1 paragraph)
     * Scope of Work (bullet points with specific deliverables)
     * Key Outcomes (bullet points with measurable results)
   
3. **Out of Scope**
   - Present as a table with columns: Scope Area | Details
   - Include areas like Development, Testing, Performance, Business Logic, etc.
   - Be specific about what is NOT included

IMPORTANT GUIDELINES:
- Write in a professional, formal business tone
- Be specific and detailed - avoid vague statements
- Use bullet points for clarity
- Include technical details where appropriate
- Base your content on the provided background, assumptions, and out-of-scope information
- Make realistic inferences when specific details are not provided, but stay aligned with the given context
- If assumptions are provided, incorporate them naturally into the scope or note them separately
- Format the output in Markdown with proper headers (##, ###) and formatting (**bold**, bullet points)

Generate the SoW document now."""

        response = client.generate(prompt=prompt, max_tokens=25000)
        
        # Extract content from SAP AI Core orchestration response
        content = ""
        
        if isinstance(response, dict):
            # SAP AI Core returns: final_result.choices[0].message.content
            if 'final_result' in response:
                final = response['final_result']
                if isinstance(final, dict) and 'choices' in final:
                    choices = final['choices']
                    if isinstance(choices, list) and len(choices) > 0:
                        choice = choices[0]
                        if isinstance(choice, dict) and 'message' in choice:
                            message = choice['message']
                            if isinstance(message, dict):
                                content = message.get('content', '')
                                if content:
                                    logger.info("✓ Extracted content from final_result.choices[0].message.content")
            
            # Fallback: try orchestration_result.choices[0].message.content
            if not content and 'orchestration_result' in response:
                orch = response['orchestration_result']
                if isinstance(orch, dict) and 'choices' in orch:
                    choices = orch['choices']
                    if isinstance(choices, list) and len(choices) > 0:
                        choice = choices[0]
                        if isinstance(choice, dict) and 'message' in choice:
                            message = choice['message']
                            if isinstance(message, dict):
                                content = message.get('content', '')
                                if content:
                                    logger.info("✓ Extracted content from orchestration_result.choices[0].message.content")
            
            # Fallback: try module_results.llm
            if not content and 'module_results' in response:
                modules = response['module_results']
                if isinstance(modules, dict) and 'llm' in modules:
                    llm_result = modules['llm']
                    if isinstance(llm_result, dict):
                        # Try choices array first
                        if 'choices' in llm_result:
                            choices = llm_result['choices']
                            if isinstance(choices, list) and len(choices) > 0:
                                choice = choices[0]
                                if isinstance(choice, dict) and 'message' in choice:
                                    content = choice['message'].get('content', '')
                                    if content:
                                        logger.info("✓ Extracted content from module_results.llm.choices[0].message.content")
                        # Try direct content field
                        if not content:
                            content = llm_result.get('content', '') or llm_result.get('text', '')
                            if content:
                                logger.info("✓ Extracted content from module_results.llm.content")
            
            # Fallback: standard OpenAI format
            if not content and 'choices' in response:
                choices = response['choices']
                if isinstance(choices, list) and len(choices) > 0:
                    choice = choices[0]
                    if isinstance(choice, dict):
                        if 'message' in choice:
                            content = choice['message'].get('content', '')
                            if content:
                                logger.info("✓ Extracted content from choices[0].message.content")
                        elif 'text' in choice:
                            content = choice['text']
                            if content:
                                logger.info("✓ Extracted content from choices[0].text")
            
            # Fallback: try direct content field
            if not content and 'content' in response:
                content_field = response['content']
                if isinstance(content_field, list) and len(content_field) > 0:
                    content = content_field[0].get('text', '') if isinstance(content_field[0], dict) else str(content_field[0])
                else:
                    content = str(content_field)
                if content:
                    logger.info("✓ Extracted content from direct content field")
            
            # Last resort: convert entire response to string
            if not content:
                logger.warning("⚠ Could not extract content from standard fields, using str(response)")
                logger.warning(f"Response keys: {list(response.keys())}")
                content = str(response)
        
        elif isinstance(response, str):
            content = response
            logger.info("✓ Response is already a string")
        else:
            content = str(response)
            logger.warning("⚠ Response is not dict or str, converting to string")
        
        # Clean up the content
        content = content.strip()
        
        # Replace escaped newlines with actual newlines if they exist as literal strings
        if '\\n' in content:
            logger.info("Converting escaped newlines...")
            content = content.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        
        logger.info(f"Final content length: {len(content)} chars")
        logger.info(f"First 300 chars: {content[:300]}")
        logger.info(f"Last 200 chars: ...{content[-200:]}")
        
        # Check if the response indicates we need more information
        # Try to parse as JSON to check for "sufficient": false
        if '{' in content and 'sufficient' in content:
            try:
                # Extract JSON portion
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                json_str = content[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                if not parsed.get('sufficient', True):
                    return SoWGenerationResponse(
                        success=False,
                        needs_more_info=True,
                        questions=parsed.get('questions', []),
                        timestamp=datetime.now().isoformat()
                    )
            except json.JSONDecodeError:
                # Not valid JSON, continue with normal flow
                pass
        
        # Final validation
        if not content or len(content) < 50:
            return SoWGenerationResponse(
                success=False,
                error="Generated content is too short or empty. Please try again.",
                needs_more_info=False,
                timestamp=datetime.now().isoformat()
            )
        
        return SoWGenerationResponse(
            success=True,
            sow_content=content,
            needs_more_info=False,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"SoW generation error: {e}")
        return SoWGenerationResponse(
            success=False,
            error=str(e),
            needs_more_info=False,
            timestamp=datetime.now().isoformat()
        )


# Save SoW Draft endpoint
class SoWDraftSaveRequest(BaseModel):
    """Request for saving SoW draft to file"""
    project_name: str
    customer: str
    background: str
    assumptions: Optional[str] = None
    out_of_scope: Optional[str] = None
    sow_content: str
    timestamp: str
    version: str = "1.0"


@app.post("/save/sow-draft")
async def save_sow_draft(request: SoWDraftSaveRequest):
    """
    Save SoW draft to the drafts folder as JSON file.
    """
    try:
        # Get the drafts folder path (relative to backend folder)
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        drafts_dir = project_root / "drafts"
        
        # Create drafts folder if it doesn't exist
        drafts_dir.mkdir(exist_ok=True)
        
        # Sanitize project name for filename
        sanitized_name = request.project_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"SoW-Draft-{sanitized_name}.json"
        filepath = drafts_dir / filename
        
        # Prepare draft data
        draft_data = {
            "project_name": request.project_name,
            "customer": request.customer,
            "background": request.background,
            "assumptions": request.assumptions,
            "out_of_scope": request.out_of_scope,
            "sow_content": request.sow_content,
            "timestamp": request.timestamp,
            "version": request.version
        }
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(draft_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"SoW draft saved: {filepath}")
        
        return {
            "success": True,
            "filename": filename,
            "path": str(filepath),
            "message": f"SoW draft saved successfully to drafts/{filename}"
        }
        
    except Exception as e:
        logger.error(f"Error saving SoW draft: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save SoW draft: {str(e)}")


# Load SoW Draft endpoint
@app.get("/load/sow-draft/{project_name}")
async def load_sow_draft(project_name: str):
    """
    Load existing SoW draft from the drafts folder by project name.
    """
    try:
        # Get the drafts folder path
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        drafts_dir = project_root / "drafts"
        
        # Sanitize project name for filename
        sanitized_name = project_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"SoW-Draft-{sanitized_name}.json"
        filepath = drafts_dir / filename
        
        # Check if file exists
        if not filepath.exists():
            return {
                "success": False,
                "exists": False,
                "message": f"No SoW draft found for project: {project_name}"
            }
        
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            draft_data = json.load(f)
        
        logger.info(f"SoW draft loaded: {filepath}")
        
        return {
            "success": True,
            "exists": True,
            "draft": draft_data,
            "filename": filename,
            "message": f"SoW draft loaded successfully from drafts/{filename}"
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing SoW draft JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON in SoW draft file: {str(e)}")
    except Exception as e:
        logger.error(f"Error loading SoW draft: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load SoW draft: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
