import os
import re
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger("inferav22-arm-profiler")

class ArmProfiler:
    """
    InferaV22 Hardware Topology & Feature Profiler
    Inspects Arm CPU capabilities, NUMA layout, HugePages, and KleidiAI support.
    """

    @staticmethod
    def get_cpu_info() -> str:
        try:
            with open("/proc/cpuinfo", "r") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    @staticmethod
    def detect_sve_width() -> int:
        """Probes SVE vector register width via lscpu or sysfs."""
        try:
            res = subprocess.run(["lscpu"], capture_output=True, text=True)
            if "sve2" in res.stdout.lower() or "sve" in res.stdout.lower():
                # Graviton4 / Axion (Neoverse V2) typically support 256-bit SVE
                # Cobalt 100 (Neoverse N2) supports 128-bit SVE
                if "neoverse-v2" in res.stdout.lower() or "c8g" in res.stdout.lower():
                    return 256
                return 128
        except Exception as e:
            logger.warning(f"Could not run lscpu: {e}")
        return 128

    @staticmethod
    def get_numa_nodes() -> Dict[str, Any]:
        """Detects NUMA topology using numactl --hardware."""
        try:
            res = subprocess.run(["numactl", "--hardware"], capture_output=True, text=True)
            if res.returncode == 0:
                nodes_match = re.search(r"available:\s+(\d+)\s+nodes", res.stdout)
                num_nodes = int(nodes_match.group(1)) if nodes_match else 1
                return {
                    "numa_nodes": num_nodes,
                    "raw_output": res.stdout
                }
        except Exception as e:
            logger.warning(f"numactl not available or failed: {e}")
        
        # Fallback inspection via sysfs
        numa_path = "/sys/devices/system/node"
        if os.path.exists(numa_path):
            nodes = [d for d in os.listdir(numa_path) if d.startswith("node")]
            return {"numa_nodes": len(nodes) or 1, "raw_output": "sysfs fallback"}
        
        return {"numa_nodes": 1, "raw_output": "single node assumption"}

    @staticmethod
    def check_hugepages() -> Dict[str, Any]:
        """Checks 2MB HugePages availability and configuration."""
        hp_path = "/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
        if os.path.exists(hp_path):
            try:
                with open(hp_path, "r") as f:
                    nr = int(f.read().strip())
                return {"available": True, "nr_hugepages": nr, "enabled": nr > 0}
            except Exception:
                pass
        return {"available": False, "nr_hugepages": 0, "enabled": False}

    @classmethod
    def profile_node(cls, cloud: str = "graviton4") -> Dict[str, Any]:
        cpu_info = cls.get_cpu_info()
        numa_info = cls.get_numa_nodes()
        sve_width = cls.detect_sve_width()
        hugepages = cls.check_hugepages()

        # Check for Arm-specific ISA extensions
        supports_dotprod = "asctime" in cpu_info or "dotprod" in cpu_info or "i8mm" in cpu_info
        supports_fp16 = "fp16" in cpu_info or "fphp" in cpu_info

        return {
            "cloud": cloud,
            "architecture": "arm64",
            "sve_width_bits": sve_width,
            "numa_nodes": numa_info["numa_nodes"],
            "supports_dotprod": supports_dotprod,
            "supports_fp16": supports_fp16,
            "kleidi_ai_compatible": supports_dotprod,
            "hugepages": hugepages,
            "recommended_threads_per_numa": (os.cpu_count() or 16) // numa_info["numa_nodes"]
        }

if __name__ == "__main__":
    profile = ArmProfiler.profile_node()
    print("InferaV22 Arm Node Profile:", profile)
