"""
Error handling and custom exceptions for the application.
"""


class ApplicationError(Exception):
    """Base application error."""
    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class DataIngestionError(ApplicationError):
    """Raised when data ingestion fails."""
    def __init__(self, message: str):
        super().__init__(message, "INGESTION_ERROR")


class ProcessingError(ApplicationError):
    """Raised when processing fails."""
    def __init__(self, message: str):
        super().__init__(message, "PROCESSING_ERROR")


class ValidationError(ApplicationError):
    """Raised when validation fails."""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class FileNotFoundError(ApplicationError):
    """Raised when a required file is not found."""
    def __init__(self, file_path: str):
        super().__init__(f"File not found: {file_path}", "FILE_NOT_FOUND")


class ConfigurationError(ApplicationError):
    """Raised when configuration is invalid."""
    def __init__(self, message: str):
        super().__init__(message, "CONFIG_ERROR")
