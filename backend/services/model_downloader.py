"""
Downloads LLM model files from HuggingFace Hub or direct HTTPS URLs.
Computes SHA256 hash for identity/caching.
"""
import hashlib
import logging
import os
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/models/cache")
HF_TOKEN = os.getenv("HF_TOKEN", "")


class ModelDownloader:

    @staticmethod
    def compute_file_hash(path: str) -> str:
        """Compute SHA256 hash of a file or directory of files."""
        sha = hashlib.sha256()
        if os.path.isfile(path):
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha.update(chunk)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for fname in sorted(files):
                    if fname.endswith((".gguf", ".safetensors", ".bin", ".model")):
                        fpath = os.path.join(root, fname)
                        sha.update(fname.encode())
                        with open(fpath, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                sha.update(chunk)
        return sha.hexdigest()

    @classmethod
    def download(cls, model_url: str) -> Dict[str, Any]:
        """
        Download the model and return local path + SHA256 hash.

        Supports:
        - HuggingFace model IDs: "org/model-name"
        - Direct HTTPS GGUF URLs: "https://...\.gguf"
        """
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

        if model_url.startswith("https://") and model_url.endswith(".gguf"):
            return cls._download_direct_gguf(model_url)
        else:
            return cls._download_huggingface(model_url)

    @classmethod
    def _download_direct_gguf(cls, url: str) -> Dict[str, Any]:
        """Download a .gguf file directly from an HTTPS URL."""
        import httpx
        filename = url.split("/")[-1].split("?")[0]  # strip query params
        local_path = os.path.join(MODEL_CACHE_DIR, filename)

        if os.path.exists(local_path):
            logger.info(f"Model already cached at {local_path}")
        else:
            logger.info(f"Downloading {url} -> {local_path}")
            with httpx.stream("GET", url, follow_redirects=True, timeout=None) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(local_path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total and downloaded % (100 * 1024 * 1024) < 65536:
                            pct = downloaded / total * 100
                            logger.info(f"Download progress: {pct:.1f}%")

        model_hash = cls.compute_file_hash(local_path)
        size_gb = os.path.getsize(local_path) / 1e9
        logger.info(f"Download complete: {local_path} ({size_gb:.2f} GB) hash={model_hash[:16]}...")
        return {
            "local_path": local_path,
            "model_hash": model_hash,
            "size_gb": round(size_gb, 2),
            "format": "gguf",
        }

    @classmethod
    def _download_huggingface(cls, model_id: str) -> Dict[str, Any]:
        """Download a HuggingFace model using huggingface_hub."""
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            raise RuntimeError(
                "huggingface-hub is not installed. Install with: pip install huggingface-hub"
            )

        # Check if GGUF files available (prefer for llama.cpp)
        try:
            from huggingface_hub import list_repo_files
            all_files = list(list_repo_files(model_id, token=HF_TOKEN or None))
            gguf_files = [f for f in all_files if f.endswith(".gguf")]
            if gguf_files:
                # Download only the GGUF files
                logger.info(f"Found {len(gguf_files)} GGUF files in {model_id}")
                local_path = snapshot_download(
                    repo_id=model_id,
                    token=HF_TOKEN or None,
                    cache_dir=MODEL_CACHE_DIR,
                    allow_patterns=["*.gguf"],
                )
            else:
                # Download full model
                local_path = snapshot_download(
                    repo_id=model_id,
                    token=HF_TOKEN or None,
                    cache_dir=MODEL_CACHE_DIR,
                    ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "rust_model*"],
                )
        except Exception as e:
            raise RuntimeError(f"Failed to download model '{model_id}' from HuggingFace: {e}")

        model_hash = cls.compute_file_hash(local_path)
        size_gb = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _, files in os.walk(local_path)
            for f in files
        ) / 1e9

        logger.info(f"Model downloaded: {local_path} ({size_gb:.2f} GB) hash={model_hash[:16]}...")
        return {
            "local_path": local_path,
            "model_hash": model_hash,
            "size_gb": round(size_gb, 2),
            "model_id": model_id,
            "format": "gguf" if gguf_files else "safetensors",
        }
