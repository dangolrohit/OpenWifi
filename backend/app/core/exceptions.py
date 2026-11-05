"""Custom application exceptions."""
from typing import Any, Optional
from fastapi import HTTPException, status

class WiFiRouterException(HTTPException):
    def __init__(self, status_code: int, detail: str, error_code: Optional[str] = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or "APP_ERROR"

class AuthenticationError(WiFiRouterException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, error_code="AUTH_FAILED")

class PermissionDeniedError(WiFiRouterException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail, error_code="PERMISSION_DENIED")

class ResourceNotFoundError(WiFiRouterException):
    def __init__(self, detail: str = "Requested resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail, error_code="NOT_FOUND")

class ValidationError(WiFiRouterException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail, error_code="VALIDATION_ERROR")

class NetworkOperationError(WiFiRouterException):
    def __init__(self, detail: str = "Network management operation failed"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail, error_code="NETWORK_ERROR")

