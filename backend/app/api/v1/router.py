"""Aggregated API v1 router."""
from fastapi import APIRouter
from .endpoints import (
    auth, dashboard, wifi, devices, filtering, bandwidth,
    guests, analytics, logs, network, system, settings
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(wifi.router)
api_router.include_router(devices.router)
api_router.include_router(filtering.router)
api_router.include_router(bandwidth.router)
api_router.include_router(guests.router)
api_router.include_router(analytics.router)
api_router.include_router(logs.router)
api_router.include_router(network.router)
api_router.include_router(system.router)
api_router.include_router(settings.router)

