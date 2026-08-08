import os
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("inferav22-llama-builder")

class LlamaArmBuilder:
    """
    Manages Arm-optimized compilation of llama.cpp and progressive model quantization.
    Configures KleidiAI kernels and target architecture flags.
    """

    def __init__(self, llamacpp_dir: str = "/tmp/llama.cpp"):
        self.llamacpp_dir = llamacpp_dir

    def generate_cmake_command(self, march: str = "armv9-a+sve+i8mm", use_kleidi: bool = True) -> str:
        flags = [
            "cmake", "-B", "build",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DLLAMA_NATIVE=ON",
            "-DLLAMA_ARM_FP16=ON",
            "-DLLAMA_NEON=ON",
            f"-DGGML_KLEIDIAI={'ON' if use_kleidi else 'OFF'}",
            f'-DCMAKE_CXX_FLAGS="-O3 -march={march} -mtune=neoverse-v2 -ffast-math"',
            f'-DCMAKE_C_FLAGS="-O3 -march={march} -mtune=neoverse-v2"'
        ]
        return " ".join(flags)

    def quantize_model(
        self,
        input_gguf: str,
        output_gguf: str,
        target_quant: str = "Q4_K_M"
    ) -> Dict[str, Any]:
        """
        Executes llama-quantize for progressive precision reduction.
        Q4_K_M is optimal for Arm 64-byte cache lines and 256-weight superblocks.
        """
        quant_bin = os.path.join(self.llamacpp_dir, "build", "bin", "llama-quantize")
        
        if not os.path.exists(quant_bin):
            raise RuntimeError(
                f"llama-quantize binary not found at '{quant_bin}'. "
                f"To run real quantization: "
                f"1) Build llama.cpp on an Arm64 Linux machine using deploy/Dockerfile.llamacpp-arm, "
                f"2) Set LLAMACPP_DIR environment variable to the build directory, "
                f"3) Ensure the 'llama-quantize' binary is at {{LLAMACPP_DIR}}/build/bin/llama-quantize. "
                f"Current LLAMACPP_DIR: {self.llamacpp_dir}"
            )

        cmd = [quant_bin, input_gguf, output_gguf, target_quant]
        logger.info(f"Executing quantization: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
            raise RuntimeError(f"Quantization failed: {res.stderr}")

        if os.path.exists(output_gguf):
            input_size = os.path.getsize(input_gguf)
            output_size = os.path.getsize(output_gguf)
            size_reduction_pct = round((1 - output_size / input_size) * 100, 1) if input_size > 0 else 0.0
        else:
            raise RuntimeError(f"Quantization completed but output file not found at {output_gguf}")

        return {
            "status": "SUCCESS",
            "input_model": input_gguf,
            "output_model": output_gguf,
            "quant_level": target_quant,
            "size_reduction_pct": size_reduction_pct,
            "log": res.stdout
        }

if __name__ == "__main__":
    builder = LlamaArmBuilder()
    cmd = builder.generate_cmake_command()
    print("Arm CMake Build Command:", cmd)
    result = builder.quantize_model("model-fp16.gguf", "model-q4km.gguf", "Q4_K_M")
    print("Quantization Result:", result)
