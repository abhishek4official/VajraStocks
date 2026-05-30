class NSEDownloaderError(Exception):
    """Base class for all exceptions in the NSE Downloader application."""
    pass

class ConfigurationError(NSEDownloaderError):
    """Raised when there is an issue loading or validating the application configuration."""
    pass

class DatabaseConnectionError(NSEDownloaderError):
    """Raised when the database connection fails or LocalDB cannot be booted/reached."""
    pass

class DatabaseExecutionError(NSEDownloaderError):
    """Raised when a database query or transaction execution fails."""
    pass

class DownloaderError(NSEDownloaderError):
    """Raised when Yahoo Finance client encounters an HTTP or parse failure."""
    pass

class RateLimitError(DownloaderError):
    """Raised when Yahoo Finance returns HTTP 429 Too Many Requests."""
    pass

class ValidationError(NSEDownloaderError):
    """Raised when downloaded data fails quality or integrity constraints."""
    pass
