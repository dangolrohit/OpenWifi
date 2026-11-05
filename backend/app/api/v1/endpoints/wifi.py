"""Wi-Fi status and access point scanning endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from ....integrations.agent_client import agent_client, AgentUnavailableError
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/wifi", tags=["Wi-Fi Settings"])

@router.get("/status")
async def get_wifi_status(user: User = Depends(get_current_user)):
    """Get upstream Wi-Fi connection metrics, signal strength, and IP details."""
    try:
        return await agent_client.get_wifi_status()
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.get("/scan")
async def scan_wifi_networks(user: User = Depends(get_current_user)):
    """Scan for available Wi-Fi access points."""
    try:
        networks = await agent_client.scan_wifi()
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"networks": networks}

