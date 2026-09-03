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
from typing import Optional, Dict, Any, List, Literal
import logging
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from llm_client import UniversalLLMClient, LLMClientError
from ibm_ica_client import IBMICAClient, IBMICAError

# Load environment variables
load_dotenv()

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

# Global LLM client instances
llm_client: Optional[UniversalLLMClient] = None
ibm_ica_client: Optional[IBMICAClient] = None

# Settings file path
SETTINGS_FILE = Path("settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "ai_provider": "sap"  # "sap" or "ibm_ica"
}

def load_settings() -> Dict[str, Any]:
    """Load settings from file or return defaults"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any]) -> bool:
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False

def get_active_provider() -> str:
    """Get the currently selected AI provider"""
    settings = load_settings()
    return settings.get("ai_provider", "sap")


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
    maw_deliverables: Optional[str] = None


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
    global llm_client, ibm_ica_client
    
    # Initialize SAP AI Core client
    try:
        llm_client = UniversalLLMClient(config_path="config.json")
        logger.info("✅ SAP AI Core LLM Client initialized successfully")
        logger.info(f"Available models: {len(llm_client.list_available_models())}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize SAP LLM client: {e}")
        llm_client = None
    
    # Initialize IBM ICA client
    try:
        ibm_endpoint = os.getenv("IBM_ICA_ENDPOINT")
        ibm_api_key = os.getenv("IBM_ICA_API_KEY")
        ibm_model_id = os.getenv("IBM_ICA_MODEL_ID", "claude-sonnet-5")
        
        if ibm_endpoint and ibm_api_key:
            ibm_ica_client = IBMICAClient(
                endpoint=ibm_endpoint,
                api_key=ibm_api_key,
                model_id=ibm_model_id
            )
            logger.info("✅ IBM ICA Client initialized successfully")
            logger.info(f"IBM ICA Model: {ibm_model_id}")
        else:
            logger.warning("⚠️  IBM ICA credentials not found in environment")
            ibm_ica_client = None
    except Exception as e:
        logger.error(f"❌ Failed to initialize IBM ICA client: {e}")
        ibm_ica_client = None
    
    # Log active provider
    active_provider = get_active_provider()
    logger.info(f"Active AI Provider: {active_provider.upper()}")


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


# Settings endpoints
class ProviderSettingsRequest(BaseModel):
    """Request to update provider settings"""
    ai_provider: str = Field(..., description="AI provider: 'sap' or 'ibm_ica'")


class ProviderSettingsResponse(BaseModel):
    """Response for provider settings"""
    success: bool
    ai_provider: str
    sap_available: bool
    ibm_ica_available: bool
    message: Optional[str] = None


@app.get("/settings/provider", response_model=ProviderSettingsResponse)
async def get_provider_settings():
    """Get current provider settings"""
    settings = load_settings()
    return ProviderSettingsResponse(
        success=True,
        ai_provider=settings.get("ai_provider", "sap"),
        sap_available=llm_client is not None,
        ibm_ica_available=ibm_ica_client is not None
    )


@app.post("/settings/provider", response_model=ProviderSettingsResponse)
async def update_provider_settings(request: ProviderSettingsRequest):
    """Update provider settings"""
    if request.ai_provider not in ["sap", "ibm_ica"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'sap' or 'ibm_ica'")
    
    # Check if the requested provider is available
    if request.ai_provider == "sap" and llm_client is None:
        raise HTTPException(status_code=503, detail="SAP AI Core client not available")
    
    if request.ai_provider == "ibm_ica" and ibm_ica_client is None:
        raise HTTPException(status_code=503, detail="IBM ICA client not available")
    
    settings = load_settings()
    settings["ai_provider"] = request.ai_provider
    
    if save_settings(settings):
        logger.info(f"Provider switched to: {request.ai_provider.upper()}")
        return ProviderSettingsResponse(
            success=True,
            ai_provider=request.ai_provider,
            sap_available=llm_client is not None,
            ibm_ica_available=ibm_ica_client is not None,
            message=f"Provider successfully switched to {request.ai_provider.upper()}"
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings")


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


# Provider wrapper for AI generation
def generate_with_active_provider(prompt: str, max_tokens: int = 25000) -> str:
    """
    Generate content using the currently selected provider.
    
    Returns the generated text content.
    Raises HTTPException if provider is not available.
    """
    active_provider = get_active_provider()
    
    if active_provider == "ibm_ica":
        if ibm_ica_client is None:
            raise HTTPException(
                status_code=503, 
                detail="IBM ICA client not initialized. Check environment variables."
            )
        
        try:
            logger.info("Generating content with IBM ICA...")
            messages = [{"role": "user", "content": prompt}]
            result = ibm_ica_client.chat(messages=messages, max_tokens=max_tokens)
            logger.info(f"IBM ICA generation completed. Tokens: {result.get('total_tokens', 'unknown')}")
            return result.get("text", "")
        except IBMICAError as e:
            logger.error(f"IBM ICA generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"IBM ICA generation failed: {str(e)}")
    
    else:  # default to SAP
        if llm_client is None:
            raise HTTPException(
                status_code=503, 
                detail="SAP AI Core client not initialized. Check configuration."
            )
        
        try:
            logger.info("Generating content with SAP AI Core...")
            response = llm_client.generate(prompt=prompt, max_tokens=max_tokens)
            
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
                
                # Last fallback: try content field directly
                if not content:
                    content = response.get('content', '')
            
            if not content:
                logger.warning("Could not extract content from SAP response")
                content = str(response)
            
            logger.info(f"SAP AI Core generation completed. Length: {len(content)}")
            return content
            
        except LLMClientError as e:
            logger.error(f"SAP generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"SAP generation failed: {str(e)}")


# Statement of Work generation endpoint
@app.post("/generate/sow", response_model=SoWGenerationResponse)
async def generate_sow(
    request: SoWGenerationRequest
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

MAW DELIVERABLES:
{request.maw_deliverables if request.maw_deliverables else "Not provided"}

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

4. **Deliverables and Work Products**
   - Analyze the MAW Deliverables provided and classify each item appropriately
   - Consider the background, scope of work, and activities to make informed classifications
   
   **Deliverables**
   - Present as a table with columns: Item | Description | Target Date/Phase
   - Include formal outputs delivered to the client (e.g., Implementation Schedule, Final Report, Training Materials, Go-Live Support Plan)
   - For each deliverable, provide a brief description and indicate when it will be delivered
   
   **Work Products**
   - Present as a separate table with columns: Item | Description | Purpose
   - Include internal or supporting documents used during project execution (e.g., Data Mapping Document, Technical Specifications, Test Scripts, Configuration Guides)
   - For each work product, provide a brief description and explain its purpose in the project
   
   - If MAW Deliverables are not provided, create a comprehensive list based on the scope and background
   - Ensure deliverables and work products align with the scope sections and key outcomes

5. **Risks**
   - Identify and document project risks based on the scope and background
   - Present as a table with columns: Risk Category | Description | Impact | Mitigation Strategy
   - Include risks such as: Technical, Schedule, Resource, Integration, Stakeholder, etc.
   - For each risk, assess impact as High/Medium/Low
   - Provide concrete mitigation strategies

6. **Dependencies**
   - Document project dependencies and prerequisites
   - Present as a table with columns: Dependency Type | Description | Owner | Status
   - Include dependencies such as: Technical, Data, Infrastructure, Team/Resource, External Systems, etc.
   - Specify who owns each dependency (IBM, Client, or Third-party)
   - Indicate status as Required, Optional, or Critical

7. **RACI Matrix**
   - Define roles and responsibilities for key project activities
   - Present as a table with columns: Activity/Task | IBM | Client
   - Use standard RACI notation:
     * R = Responsible (does the work)
     * A = Accountable (final approval)
     * C = Consulted (provides input)
     * I = Informed (kept updated)
   - Include activities such as:
     * Project Planning & Kick-off
     * Requirements Gathering
     * Solution Design
     * Development/Implementation
     * Testing & Quality Assurance
     * User Acceptance Testing (UAT)
     * Deployment & Go-Live
     * Training & Knowledge Transfer
     * Documentation
     * Project Sign-off
   - Ensure clear accountability for each activity

IMPORTANT GUIDELINES:
- Write in a professional, formal business tone
- Be specific and detailed - avoid vague statements
- Use bullet points for clarity
- Include technical details where appropriate
- Base your content on the provided background, assumptions, out-of-scope information, and MAW deliverables
- When classifying deliverables vs. work products, consider:
  * Deliverables are formal outputs given to the client or used for project governance
  * Work Products are intermediate artifacts created during project execution
- Make realistic inferences when specific details are not provided, but stay aligned with the given context
- If assumptions are provided, incorporate them naturally into the scope or note them separately
- Format the output in Markdown with proper headers (##, ###) and formatting (**bold**, bullet points)
- Use tables with proper markdown syntax (| column | column |) for structured information

Generate the SoW document now."""

        # Use the provider wrapper to generate content
        content = generate_with_active_provider(prompt=prompt, max_tokens=25000)
        
        # Clean up the content
        content = content.strip()
        
        # Replace escaped newlines with actual newlines if they exist as literal strings
        if '\\n' in content:
            logger.info("Converting escaped newlines...")
            content = content.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        
        logger.info(f"Final content length: {len(content)} chars")
        
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


# Configuration Management Endpoints

class ProviderConfig(BaseModel):
    provider: str = Field(..., description="Provider name: anthropic, openai, or google_gemini")
    api_key: str = Field(..., description="API key for the provider")
    enabled: bool = Field(default=True, description="Enable this provider")


@app.get("/config/providers")
async def get_provider_config():
    """
    Get current provider configuration status.
    """
    try:
        backend_dir = Path(__file__).parent
        config_path = backend_dir / "config.json"
        
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Extract provider status
        providers = {}
        for provider_key in ['anthropic', 'openai', 'google_gemini']:
            if provider_key in config.get('models', {}):
                provider_data = config['models'][provider_key]
                providers[provider_key] = {
                    'enabled': provider_data.get('enabled', False),
                    'provider': provider_data.get('provider', ''),
                    'has_api_key': bool(os.getenv(provider_data.get('auth', {}).get('api_key_env', '')))
                }
        
        return {
            "success": True,
            "providers": providers,
            "default_provider": config.get('settings', {}).get('default_provider', 'sap_ai_core')
        }
        
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read configuration: {str(e)}")


@app.post("/config/update-provider")
async def update_provider_config(config_data: ProviderConfig):
    """
    Update provider configuration with API key.
    Updates both config.json and .env file.
    """
    try:
        backend_dir = Path(__file__).parent
        config_path = backend_dir / "config.json"
        env_path = backend_dir / ".env"
        
        # Validate provider
        valid_providers = {
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'google_gemini': 'GOOGLE_API_KEY'
        }
        
        if config_data.provider not in valid_providers:
            raise HTTPException(status_code=400, detail=f"Invalid provider. Must be one of: {', '.join(valid_providers.keys())}")
        
        # Update config.json
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        provider_key = config_data.provider
        if provider_key not in config.get('models', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_key} not found in config")
        
        # Enable the provider
        config['models'][provider_key]['enabled'] = config_data.enabled
        
        # If this is being enabled, also enable the first model
        if config_data.enabled and config['models'][provider_key].get('models'):
            config['models'][provider_key]['models'][0]['enabled'] = True
        
        # Save updated config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        # Update or create .env file
        env_key = valid_providers[config_data.provider]
        env_lines = []
        key_found = False
        
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
            
            # Update existing key
            for i, line in enumerate(env_lines):
                if line.strip().startswith(f"{env_key}="):
                    env_lines[i] = f"{env_key}={config_data.api_key}\n"
                    key_found = True
                    break
        
        # Add key if not found
        if not key_found:
            env_lines.append(f"{env_key}={config_data.api_key}\n")
        
        # Write .env file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        # Update environment variable in current process
        os.environ[env_key] = config_data.api_key
        
        logger.info(f"Updated configuration for provider: {config_data.provider}")
        
        return {
            "success": True,
            "message": f"Successfully updated {config_data.provider} configuration",
            "provider": config_data.provider,
            "enabled": config_data.enabled,
            "restart_required": True
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON in config file: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


# Public Holidays endpoint
HOLIDAYS_REGION_FILES = {
    "vic_australia": "holidays_vic_australia.json",
    "india": "holidays_india.json",
}


class HolidaysParseRequest(BaseModel):
    """Request to parse pasted holiday text into a JSON file for a region"""
    region: Literal["vic_australia", "india"]
    raw_text: str


@app.post("/holidays/parse")
async def parse_holidays(request: HolidaysParseRequest):
    """
    Use the active AI provider to parse pasted holiday text (copied from a
    webpage or spreadsheet) into structured holiday data for the current
    year only, then overwrite the region's JSON file under backend/data/.
    """
    try:
        if not request.raw_text.strip():
            raise HTTPException(status_code=400, detail="No holiday text provided")

        current_year = datetime.now().year
        region_label = "Victoria, Australia" if request.region == "vic_australia" else "India"

        prompt = f"""You are given raw text copied from a webpage or spreadsheet listing public holidays for {region_label}.

Extract only the holidays that fall in the year {current_year}.

Raw text:
---
{request.raw_text}
---

Return ONLY a JSON array (no markdown, no explanation) where each item has this shape:
{{"date": "YYYY-MM-DD", "name": "Holiday Name"}}

Sort the array by date ascending. If a holiday has no clear date or is not in {current_year}, omit it."""

        content = generate_with_active_provider(prompt=prompt, max_tokens=4000)
        content = content.strip()

        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx == -1 or end_idx <= start_idx:
            raise HTTPException(status_code=500, detail="AI response did not contain a JSON array")

        json_str = content[start_idx:end_idx]
        holidays = json.loads(json_str)

        backend_dir = Path(__file__).parent
        data_dir = backend_dir / "data"
        data_dir.mkdir(exist_ok=True)

        filepath = data_dir / HOLIDAYS_REGION_FILES[request.region]
        holiday_data = {
            "region": region_label,
            "year": current_year,
            "holidays": holidays,
            "updated_at": datetime.now().isoformat()
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(holiday_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Holidays saved for {region_label}: {filepath} ({len(holidays)} entries)")

        return {
            "success": True,
            "region": request.region,
            "year": current_year,
            "count": len(holidays),
            "holidays": holidays
        }

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing holidays JSON from AI response: {e}")
        raise HTTPException(status_code=500, detail=f"Could not parse AI response as JSON: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Holidays parse error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse holidays: {str(e)}")


@app.get("/holidays/{region}")
async def get_holidays(region: Literal["vic_australia", "india"]):
    """Load the saved holidays JSON for a region, if it exists."""
    backend_dir = Path(__file__).parent
    filepath = backend_dir / "data" / HOLIDAYS_REGION_FILES[region]

    if not filepath.exists():
        return {"success": True, "region": region, "year": datetime.now().year, "holidays": []}

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {"success": True, **data}


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
