from fastapi import Request
from .services.sap_client import SAPAIClient
from .services.agent_service import AgentService
from .services.session_service import SessionService


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_sap_client(request: Request) -> SAPAIClient:
    return request.app.state.sap_client
