"""Network interface, subnet, routing, and NAT status endpoints."""
from fastapi import APIRouter, Depends
from ....integrations.agent_client import agent_client
from ...dependencies.auth import get_current_user
from ....models.user import User

router = APIRouter(prefix="/network", tags=["Network Settings"])

@router.get("/interfaces")
async def list_network_interfaces(user: User = Depends(get_current_user)):
    """List physical and virtual network interfaces with IP and link states."""
    interfaces = await agent_client.get_interfaces()
    return {"interfaces": interfaces}

@router.get("/routes")
async def get_routing_table(user: User = Depends(get_current_user)):
    """Inspect system routing table and verify default upstream gateway."""
    return await agent_client.get_routes()

