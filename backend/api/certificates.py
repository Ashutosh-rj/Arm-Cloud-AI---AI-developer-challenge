import logging
from fastapi import APIRouter, HTTPException, Depends
from auth.middleware import require_auth, optional_auth
from core.validators import validate_run_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Certificates"])

@router.get("/certificates/{cert_id}")
async def get_certificate(
    cert_id: str,
    user: dict = Depends(optional_auth),
):
    """Retrieve an optimization certificate by ID. Publicly accessible for verification."""
    from db.runs_repository import RunsRepository
    cert = await RunsRepository.get_certificate(cert_id)
    if not cert:
        raise HTTPException(404, f"Certificate '{cert_id}' not found or expired")
    return cert

@router.get("/certificates/{cert_id}/verify")
async def verify_certificate(
    cert_id: str,
):
    """Publicly verify the integrity of a certificate using its SHA256 signature."""
    from db.runs_repository import RunsRepository
    from services.certificate_service import CertificateService
    cert = await RunsRepository.get_certificate(cert_id)
    if not cert:
        raise HTTPException(404, f"Certificate '{cert_id}' not found or expired")
    is_valid = CertificateService.verify_signature(cert)
    return {
        "certificate_id": cert_id,
        "valid": is_valid,
        "model_url": cert.get("model_url"),
        "issued_at": cert.get("generated_at"),
        "verification_message": "Signature is valid — certificate data has not been tampered with." if is_valid else "INVALID — certificate data has been modified after issuance."
    }
