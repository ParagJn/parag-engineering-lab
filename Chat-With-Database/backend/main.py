import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent import set_engine, get_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def build_error_detail(
    *,
    code: str,
    title: str,
    message: str,
    suggestions: list[str] | None = None,
    issues: list[dict[str, str]] | None = None,
    technical_details: str | None = None,
):
    return {
        "code": code,
        "title": title,
        "message": message,
        "suggestions": _dedupe(suggestions or []),
        "issues": issues or [],
        "technical_details": technical_details,
    }


def classify_db_connection_error(exc: Exception):
    raw = " ".join(str(exc).split())
    lowered = raw.lower()

    issues: list[dict[str, str]] = []
    suggestions: list[str] = []

    def add_issue(label: str, detail: str):
        issues.append({"label": label, "detail": detail})

    if "password authentication failed" in lowered or "access denied for user" in lowered:
        add_issue(
            "Authentication failed",
            "The database rejected the supplied username or password.",
        )
        suggestions.extend([
            "Verify the username and password exactly as configured in the database.",
            "If this is a managed database, reset the user password and try again.",
            "Confirm that the selected user is allowed to log in from external clients.",
        ])

    if "no pg_hba.conf entry" in lowered:
        add_issue(
            "Host access blocked",
            "PostgreSQL is rejecting this client host before the session can be opened.",
        )
        suggestions.extend([
            "Allow your current client IP in PostgreSQL pg_hba.conf or the cloud database access rules.",
            "If this is AWS RDS, verify the security group, public accessibility, and inbound rules for port 5432.",
        ])

    if "no encryption" in lowered or "ssl" in lowered and "required" in lowered:
        add_issue(
            "Encryption mismatch",
            "The server appears to require SSL/TLS or is rejecting the current connection mode.",
        )
        suggestions.extend([
            "Use SSL/TLS settings that match the database server requirements.",
            "For managed PostgreSQL instances, confirm whether SSL is required for client connections.",
        ])

    if "could not translate host name" in lowered or "name or service not known" in lowered or "unknown mysql server host" in lowered:
        add_issue(
            "Host could not be resolved",
            "The hostname could not be translated into an IP address.",
        )
        suggestions.extend([
            "Check for typos in the host name.",
            "Confirm the DNS name is reachable from the machine running the backend.",
        ])

    if "connection refused" in lowered or "can't connect to mysql server" in lowered:
        add_issue(
            "Connection refused",
            "The server was reached, but it is not accepting connections on that host/port.",
        )
        suggestions.extend([
            "Confirm the database server is running and listening on the configured port.",
            "Verify there is no firewall or network policy blocking the backend from reaching the database.",
        ])

    if "timed out" in lowered or "timeout expired" in lowered:
        add_issue(
            "Connection timed out",
            "The backend could not establish a connection before the timeout window elapsed.",
        )
        suggestions.extend([
            "Check whether the database host is reachable from the backend network.",
            "Verify security groups, firewalls, VPN rules, or private subnet restrictions.",
        ])

    if "database" in lowered and "does not exist" in lowered:
        add_issue(
            "Database name not found",
            "The target database does not exist or is not visible to this user.",
        )
        suggestions.extend([
            "Verify the database name exactly, including capitalization where relevant.",
            "Make sure the selected user has permission to connect to that database.",
        ])

    if not issues:
        add_issue(
            "Database connection failed",
            "The backend could not establish a usable connection with the supplied settings.",
        )
        suggestions.extend([
            "Double-check the host, port, database name, username, and password.",
            "Verify the backend machine can reach the database over the network.",
        ])

    return build_error_detail(
        code="db_connection_failed",
        title="Unable to connect to the database",
        message="The connection settings were received, but the database rejected or blocked the connection. Review the issues below and adjust the credentials or access rules before trying again.",
        suggestions=suggestions,
        issues=issues,
        technical_details=raw,
    )


def build_session_error_detail(message: str):
    return build_error_detail(
        code="session_not_found",
        title="Database session missing",
        message="No active database session is available for this chat request.",
        suggestions=[
            "Reconnect to the database from the connection screen.",
            "If the backend was restarted, create a new session before sending chat messages.",
        ],
        issues=[{"label": "Session lookup failed", "detail": message}],
        technical_details=message,
    )


def build_chat_error_detail(exc: Exception):
    raw = " ".join(str(exc).split())
    lowered = raw.lower()

    if "create_react_agent" in raw and "unexpected keyword" in lowered:
        return build_error_detail(
            code="agent_configuration_incompatible",
            title="Backend agent configuration is incompatible",
            message="The backend is using a LangGraph agent configuration that does not match the installed package version.",
            suggestions=[
                "Update the backend agent construction to match the installed LangGraph API.",
                "Restart the backend after dependency or code changes.",
            ],
            issues=[
                {
                    "label": "Agent API mismatch",
                    "detail": "The installed LangGraph create_react_agent signature does not accept one of the supplied arguments.",
                }
            ],
            technical_details=raw,
        )

    if "anthropic_api_key is not configured" in lowered or (
        "api_key" in lowered and "not configured" in lowered
    ) or "expected either api_key or auth_token to be set" in lowered:
        return build_error_detail(
            code="missing_ai_api_key",
            title="AI provider key is missing",
            message="Chat cannot run because the backend does not have an Anthropic API key configured.",
            suggestions=[
                "Add ANTHROPIC_API_KEY to backend/.env.",
                "Restart the backend after updating the environment file.",
                "Verify the key is loaded in the same environment where FastAPI is running.",
            ],
            issues=[
                {
                    "label": "Missing configuration",
                    "detail": "The backend tried to initialize the chat model without a valid API key.",
                }
            ],
            technical_details=raw,
        )

    if "authentication_error" in lowered or "invalid x-api-key" in lowered or "unauthorized" in lowered:
        return build_error_detail(
            code="invalid_ai_api_key",
            title="AI provider authentication failed",
            message="The backend reached the AI provider, but the configured API key was rejected.",
            suggestions=[
                "Verify that ANTHROPIC_API_KEY is correct and active.",
                "If the key was recently rotated, update backend/.env and restart the backend.",
            ],
            issues=[
                {
                    "label": "Authentication rejected",
                    "detail": "The AI provider did not accept the configured credentials.",
                }
            ],
            technical_details=raw,
        )

    if "rate limit" in lowered or "429" in lowered:
        return build_error_detail(
            code="ai_rate_limited",
            title="AI provider rate limit reached",
            message="The AI provider temporarily rejected the request because the usage limit was reached.",
            suggestions=[
                "Wait briefly and try again.",
                "Check the provider account limits, quota, or billing status.",
            ],
            issues=[
                {
                    "label": "Request throttled",
                    "detail": "The chat request exceeded the current API rate or usage threshold.",
                }
            ],
            technical_details=raw,
        )

    return build_error_detail(
        code="chat_processing_failed",
        title="Chat request failed",
        message="The backend could not finish processing this chat request.",
        suggestions=[
            "Try sending the message again.",
            "If the problem persists, reconnect to the database and retry.",
        ],
        issues=[{"label": "Processing error", "detail": str(exc)}],
        technical_details=str(exc),
    )

app = FastAPI(title="Chat With Database API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For POC, allow all. In prod, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DBConfig(BaseModel):
    db_type: str
    host: str
    port: int
    user: str
    password: str
    db_name: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    session_id: str

@app.post("/api/config")
async def configure_db(config: DBConfig):
    try:
        session_id = str(uuid.uuid4())
        set_engine(
            session_id=session_id,
            db_type=config.db_type,
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            db_name=config.db_name
        )
        return {"session_id": session_id, "message": "Database configured successfully."}
    except Exception as e:
        logger.exception("Error configuring DB")
        raise HTTPException(status_code=400, detail=classify_db_connection_error(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        agent = get_agent(request.session_id)
        
        # We pass the input to the agent
        response = agent.invoke({"messages": [HumanMessage(content=request.message)]})
        
        # Extract the last AIMessage content
        last_message = response["messages"][-1]
        
        return ChatResponse(response=last_message.content, session_id=request.session_id)
        
    except ValueError as ve:
        raise HTTPException(status_code=401, detail=build_session_error_detail(str(ve)))
    except Exception as e:
        logger.exception("Error executing chat")
        raise HTTPException(status_code=500, detail=build_chat_error_detail(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
