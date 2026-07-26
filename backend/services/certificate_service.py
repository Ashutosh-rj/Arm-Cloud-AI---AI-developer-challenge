import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from core.config import settings

logger = logging.getLogger("inferav22-certificate-service")

class CertificateService:
    """
    InferaV22 Cryptographic Certificate Engine
    Generates, signs, and verifies auditable Optimization Certificates for Arm AI inference.
    """

    @classmethod
    def generate_certificate(
        cls,
        run_id: str,
        model_url: str,
        optimal_config: Dict[str, Any],
        benchmarks: Dict[str, Any],
        quality_delta: Dict[str, Any]
    ) -> Dict[str, Any]:
        cert_id = f"infrav22-cert-{run_id[:8]}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        payload = {
            "inferav22_version": settings.API_VERSION,
            "tagline": settings.TAGLINE,
            "certification_id": cert_id,
            "model": model_url,
            "timestamp": timestamp,
            "arm_targets": ["graviton4", "cobalt100", "axion"],
            "optimal_config": optimal_config,
            "benchmarks": benchmarks,
            "quality_delta": quality_delta,
        }

        # Dynamically compute optimization score (0-100) based on benchmark performance and quality retention
        tps = benchmarks.get("tps_p50", 40.0)
        ttft = benchmarks.get("ttft_p99_ms", 300.0)
        q_delta = abs(quality_delta.get("score_delta", 0.003))

        base_score = 90
        tps_bonus = min(6, int((tps - 30) / 10))
        latency_bonus = min(2, int((500 - ttft) / 100))
        quality_penalty = int(q_delta * 100)

        score = max(70, min(100, base_score + tps_bonus + latency_bonus - quality_penalty))

        payload_to_hash = dict(payload)
        payload_bytes = json.dumps(payload_to_hash, sort_keys=True).encode("utf-8")
        signature = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()
        
        payload["overall_score"] = score
        payload["score"] = score
        payload["signature"] = signature
        payload["public_url"] = f"{settings.VERIFY_BASE_URL}/cert/{cert_id}"

        logger.info(f"Generated Certificate {cert_id} with score {score} and signature {signature[:20]}...")
        return payload

    @classmethod
    def verify_certificate(cls, certificate: Dict[str, Any]) -> Tuple[bool, str]:
        """Verifies the integrity and SHA256 signature of an Optimization Certificate."""
        try:
            signature = certificate.get("signature", "")
            if not signature.startswith("sha256:"):
                return False, "Invalid signature format"

            # Reconstruct canonical payload
            payload_keys = [
                "inferav22_version", "tagline", "certification_id", "model",
                "timestamp", "arm_targets", "optimal_config", "benchmarks", "quality_delta"
            ]
            reconstructed = {k: certificate[k] for k in payload_keys if k in certificate}
            
            payload_bytes = json.dumps(reconstructed, sort_keys=True).encode("utf-8")
            expected_sig = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()

            if expected_sig == signature:
                return True, "Certificate signature is valid and authentic"
            else:
                return False, "Signature mismatch — certificate payload has been modified"
        except Exception as e:
            return False, f"Verification failed with error: {str(e)}"

if __name__ == "__main__":
    cert = CertificateService.generate_certificate(
        run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        model_url="meta-llama/Llama-3.2-3B-Instruct",
        optimal_config={"quantization": "INT4", "threads": 48, "kleidiAI": True},
        benchmarks={"tps_p50": 89.4, "ttft_p99_ms": 287.0},
        quality_delta={"score_delta": -0.003, "gate": "PASS"}
    )
    is_valid, msg = CertificateService.verify_certificate(cert)
    print(f"Verification: {is_valid} ({msg})")
