import re
import ipaddress
import logging
from urllib.parse import urlparse
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# HuggingFace model ID: org/model-name (alphanumeric, hyphens, dots, underscores)
HF_MODEL_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]{0,95}/[a-zA-Z0-9][a-zA-Z0-9_\-\.]{0,95}$')
# HTTPS URL for direct GGUF downloads
HTTPS_GGUF_PATTERN = re.compile(r'^https://[a-zA-Z0-9\-\.]{1,253}/[\w/\-\.]+\.gguf$', re.IGNORECASE)

# Private IP ranges that must be blocked (SSRF prevention)
PRIVATE_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 unique local
]

def _is_private_or_loopback(hostname: str) -> bool:
    """Returns True if hostname resolves to a private/loopback IP."""
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in net for net in PRIVATE_RANGES) or addr.is_loopback or addr.is_link_local
    except ValueError:
        # Not an IP address — it's a hostname. We can't resolve it here without
        # blocking I/O. Trust DNS + network policies in production, but block
        # obvious patterns.
        suspicious_hosts = ['localhost', '0.0.0.0', 'metadata.google.internal', '169.254.169.254']
        return hostname.lower() in suspicious_hosts

def validate_model_url(model_url: str) -> str:
    """
    Validates that model_url is a safe HuggingFace model ID or HTTPS GGUF URL.
    Raises HTTPException(400) for invalid or potentially dangerous values.
    Returns the validated model_url on success.
    """
    if not model_url or not isinstance(model_url, str):
        raise HTTPException(status_code=400, detail="model_url must be a non-empty string")

    model_url = model_url.strip()

    if len(model_url) > 512:
        raise HTTPException(status_code=400, detail="model_url is too long (max 512 chars)")

    # Check for path traversal sequences
    traversal_patterns = ['../', '..\\', '%2e%2e', '%252e']
    for pattern in traversal_patterns:
        if pattern.lower() in model_url.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Path traversal sequence '{pattern}' detected in model_url"
            )

    # Case 1: HuggingFace model ID (e.g., "meta-llama/Llama-3.2-3B-Instruct")
    if HF_MODEL_PATTERN.match(model_url):
        logger.debug(f"Validated model_url as HuggingFace ID: {model_url}")
        return model_url

    # Case 2: HTTPS URL pointing to a .gguf file
    if HTTPS_GGUF_PATTERN.match(model_url):
        parsed = urlparse(model_url)
        hostname = parsed.hostname or ""

        if _is_private_or_loopback(hostname):
            raise HTTPException(
                status_code=400,
                detail=f"SSRF blocked: '{hostname}' resolves to a private/loopback address"
            )

        logger.debug(f"Validated model_url as HTTPS GGUF URL: {model_url}")
        return model_url

    raise HTTPException(
        status_code=400,
        detail=(
            f"Invalid model_url format: '{model_url}'. "
            "Expected either a HuggingFace model ID (e.g., 'org/model-name') "
            "or an HTTPS URL ending in .gguf (e.g., 'https://example.com/model.gguf')"
        )
    )

def validate_run_id(run_id: str) -> str:
    """Validates that run_id is a valid UUID string."""
    import uuid
    try:
        uuid.UUID(run_id)
        return run_id
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid run_id format: '{run_id}'")

def validate_cloud_name(cloud: str) -> str:
    """Validates that cloud is one of the supported platforms."""
    allowed = {"graviton4", "cobalt100", "axion"}
    if cloud.lower() not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cloud '{cloud}'. Must be one of: {', '.join(sorted(allowed))}"
        )
    return cloud.lower()
