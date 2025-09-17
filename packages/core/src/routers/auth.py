"""
Authentication router - placeholder for Story 4.

This will be implemented in Story 4: User Registration and Authentication
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def auth_status():
    """Placeholder endpoint - will be implemented in Story 4."""
    return {"message": "Auth router placeholder - Story 4 implementation pending"}
