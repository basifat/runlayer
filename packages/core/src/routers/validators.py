"""
Validators router - placeholder for Story 7.

This will be implemented in Story 7: Basic Validator Framework
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def validators_status():
    """Placeholder endpoint - will be implemented in Story 7."""
    return {"message": "Validators router placeholder - Story 7 implementation pending"}
