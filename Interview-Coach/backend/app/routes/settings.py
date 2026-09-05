from fastapi import APIRouter, Depends, HTTPException, Request

from ..models.settings import PublicSettings, SettingsUpdateRequest, SettingsVerificationResponse
from ..services.sap_client import SAPAIClient
from ..services.settings_service import SettingsService

router = APIRouter()


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_sap_client(request: Request) -> SAPAIClient:
    return request.app.state.sap_client


@router.get("/", response_model=PublicSettings, summary="Get AI provider settings")
async def get_settings(settings_svc: SettingsService = Depends(get_settings_service)):
    settings = await settings_svc.get_settings()
    return settings_svc.to_public_settings(settings)


@router.put("/", response_model=PublicSettings, summary="Update AI provider settings")
async def update_settings(
    request_body: SettingsUpdateRequest,
    settings_svc: SettingsService = Depends(get_settings_service),
):
    try:
        settings = await settings_svc.update_settings(
            provider_mode=request_body.provider_mode,
            api_keys=request_body.api_keys.model_dump(),
            enabled_providers=request_body.enabled_providers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings_svc.to_public_settings(settings)


@router.post("/verify", response_model=SettingsVerificationResponse, summary="Verify enabled custom API keys")
async def verify_settings(
    request_body: SettingsUpdateRequest,
    settings_svc: SettingsService = Depends(get_settings_service),
    sap_client: SAPAIClient = Depends(get_sap_client),
):
    saved = await settings_svc.get_settings()
    merged_keys = saved.get("api_keys", {}).copy()
    for provider, value in request_body.api_keys.model_dump().items():
        incoming = (value or "").strip()
        if incoming:
            merged_keys[provider] = incoming

    enabled = request_body.enabled_providers or [
        provider for provider in ("openai", "anthropic", "gemini") if merged_keys.get(provider)
    ]
    verification_settings = {
        "provider_mode": "custom",
        "api_keys": merged_keys,
        "enabled_providers": enabled,
    }

    try:
        results = await sap_client.verify_custom_providers(verification_settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": all(item["ok"] for item in results),
        "results": results,
    }
