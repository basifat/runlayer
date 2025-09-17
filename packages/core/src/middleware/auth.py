"""
Authentication middleware for JWT token validation.

Handles JWT access tokens and refresh tokens with automatic refresh.
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from ..config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware."""
    
    # Routes that don't require authentication
    PUBLIC_ROUTES = {
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/proofs/public"  # Public proof viewing
    }
    
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
    
    def is_public_route(self, path: str) -> bool:
        """Check if route is public (doesn't require authentication)."""
        # Exact matches
        if path in self.PUBLIC_ROUTES:
            return True
        
        # Pattern matches
        public_patterns = [
            "/api/v1/proofs/public/",  # Public proof pages
            "/static/",  # Static files
        ]
        
        for pattern in public_patterns:
            if path.startswith(pattern):
                return True
        
        return False
    
    def extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                return None
            return token
        except ValueError:
            return None
    
    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                return None
            
            return payload
            
        except jwt.InvalidTokenError:
            return None
    
    def create_error_response(self, message: str, status_code: int = 401) -> JSONResponse:
        """Create standardized error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": status_code,
                    "message": message,
                    "type": "authentication_error"
                }
            }
        )
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for public routes
        if self.is_public_route(request.url.path):
            return await call_next(request)
        
        # Extract token
        token = self.extract_token(request)
        if not token:
            return self.create_error_response("Missing authentication token")
        
        # Decode and validate token
        payload = self.decode_token(token)
        if not payload:
            return self.create_error_response("Invalid or expired token")
        
        # Extract user information from token
        user_id = payload.get("sub")  # Subject (user ID)
        email = payload.get("email")
        workspace_id = payload.get("workspace_id")
        roles = payload.get("roles", [])
        
        if not user_id:
            return self.create_error_response("Invalid token payload")
        
        # Store user information in request state
        request.state.user_id = user_id
        request.state.user_email = email
        request.state.workspace_id = workspace_id
        request.state.user_roles = roles
        request.state.is_authenticated = True
        
        # Add user context to structured logging
        import structlog
        structlog.contextvars.bind_contextvars(
            user_id=user_id,
            workspace_id=workspace_id
        )
        
        return await call_next(request)
