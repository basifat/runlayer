"""
Users router - placeholder for Story 5.

This will be implemented in Story 5: Basic User Profile Management
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def users_status():
    """Placeholder endpoint - will be implemented in Story 5."""
    return {"message": "Users router placeholder - Story 5 implementation pending"}
