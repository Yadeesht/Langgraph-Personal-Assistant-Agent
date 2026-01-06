"""
OAuth configuration and stateless mode detection.

Stateless mode is enabled when:
1. Environment variable STATELESS_MODE=true
2. Running in Docker/container environment
3. No local filesystem access for temp files
"""

import os


def is_stateless_mode() -> bool:
    """
    Check if the application is running in stateless mode.

    Stateless mode is enabled when:
    - STATELESS_MODE environment variable is set to 'true' or '1'
    - DOCKER_ENV environment variable is set (indicates Docker container)
    - Running on cloud platforms (AWS Lambda, Google Cloud Functions, etc.)

    Returns:
        bool: True if running in stateless mode
    """
    # Explicit stateless mode flag
    stateless_env = os.getenv("STATELESS_MODE", "").lower()
    if stateless_env in ("true", "1", "yes"):
        return True

    # Check for Docker environment
    if os.getenv("DOCKER_ENV") or os.path.exists("/.dockerenv"):
        return True

    # Check for cloud platform indicators
    cloud_indicators = [
        "AWS_LAMBDA_FUNCTION_NAME",  # AWS Lambda
        "FUNCTION_NAME",  # Google Cloud Functions
        "K_SERVICE",  # Google Cloud Run
        "AZURE_FUNCTIONS_ENVIRONMENT",  # Azure Functions
    ]

    if any(os.getenv(indicator) for indicator in cloud_indicators):
        return True

    return False


def get_temp_file_strategy() -> str:
    """
    Get the temporary file handling strategy based on environment.

    Returns:
        str: 'memory' for stateless mode, 'disk' for stateful mode
    """
    return "memory" if is_stateless_mode() else "disk"


def log_environment_info():
    """Log current environment configuration for debugging."""
    from utils.helper import setup_logger

    logger = setup_logger(__name__)

    mode = "STATELESS" if is_stateless_mode() else "STATEFUL"
    strategy = get_temp_file_strategy()

    logger.info(f"🔧 Running in {mode} mode")
    logger.info(f"📁 Temp file strategy: {strategy}")

    if is_stateless_mode():
        logger.info("⚠️  File operations will use in-memory buffers")
        logger.info(
            "💡 For large files, consider using HTTP/HTTPS URLs instead of file:// URLs"
        )
