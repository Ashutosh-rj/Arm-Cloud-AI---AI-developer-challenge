import logging
from typing import Dict, Any

logger = logging.getLogger("inferav22-helm-generator")

class HelmGenerator:
    """
    InferaV22 Deployment Engine
    Generates Kubernetes Helm chart configurations tuned for Arm64 node pools.
    """

    @classmethod
    def generate_helm_values(
        cls,
        model_url: str,
        quant_level: str = "INT4",
        threads: int = 48,
        numa_bind: bool = True
    ) -> Dict[str, Any]:
        return {
            "appName": "inferav22-inference-server",
            "replicaCount": 3,
            "image": {
                "repository": "ghcr.io/inferav22/llamacpp-arm",
                "tag": "latest",
                "pullPolicy": "IfNotPresent"
            },
            "nodeSelector": {
                "kubernetes.io/arch": "arm64",
                "node.kubernetes.io/instance-type": "c8g.4xlarge"
            },
            "resources": {
                "requests": {
                    "cpu": f"{threads}",
                    "memory": "8Gi"
                },
                "limits": {
                    "cpu": f"{threads}",
                    "memory": "16Gi"
                }
            },
            "env": [
                {"name": "GGML_USE_KLEIDIAI", "value": "1"},
                {"name": "MODEL_URL", "value": model_url},
                {"name": "QUANT_LEVEL", "value": quant_level},
                {"name": "NUMA_BIND", "value": str(numa_bind).lower()}
            ],
            "autoscaling": {
                "enabled": True,
                "minReplicas": 2,
                "maxReplicas": 10,
                "targetCPUUtilizationPercentage": 80
            }
        }

    @classmethod
    def generate_helm_manifests(cls, model_url: str, quant_level: str = "INT4") -> Dict[str, Any]:
        values = cls.generate_helm_values(model_url, quant_level)
        return {
            "chart_name": "inferav22-inference-server",
            "version": "1.0.0",
            "values": values,
            "manifest_files": ["deployment.yaml", "service.yaml", "hpa.yaml", "daemonset-numa.yaml"]
        }

if __name__ == "__main__":
    values = HelmGenerator.generate_helm_values("meta-llama/Llama-3.2-3B-Instruct")
    print("Helm Chart Values:", values)
