"""Piper local text-to-speech provider tool."""

from __future__ import annotations

import time
import wave
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class PiperTTS(BaseTool):
    name = "piper_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "piper"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["pip:piper-tts"]
    install_instructions = (
        "Install Piper TTS:\n"
        "  pip install piper-tts\n"
        "Then download a voice model:\n"
        "  python -m piper.download en_US-kathleen-low\n"
        "Or place a .onnx model file in assets/voices/"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": False,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "offline narration fallback",
        "privacy-sensitive local-only workflows",
    ]
    not_good_for = [
        "best-in-class expressive voice quality",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "model": {
                "type": "string",
                "default": "en_US-kathleen-low",
            },
            "speaker_id": {
                "type": "integer",
                "default": 0,
            },
            "length_scale": {
                "type": "number",
                "default": 1.0,
            },
            "sentence_silence": {
                "type": "number",
                "default": 0.3,
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=200, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "model", "speaker_id", "length_scale"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for intelligibility"]

    def get_status(self) -> ToolStatus:
        try:
            import piper  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Piper TTS not available. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Local TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _resolve_model_path(self, model: str) -> Path | None:
        candidate = Path(model)
        if candidate.suffix == ".onnx":
            return candidate if candidate.exists() else None
        onnx_candidate = candidate.with_suffix(".onnx")
        if onnx_candidate.exists():
            return onnx_candidate
        model_file = f"{model}.onnx"
        search_dirs = [
            Path(__file__).parent.parent.parent / "assets" / "voices",
            Path.home() / ".local" / "share" / "piper",
            Path.home() / ".piper" / "models",
            Path.cwd(),
        ]
        for data_dir in search_dirs:
            hit = data_dir / model_file
            if hit.exists():
                return hit
        return None

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        from piper import PiperVoice, SynthesisConfig

        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        model_name = inputs.get("model", "en_US-kathleen-low")
        model_path = self._resolve_model_path(model_name)
        if model_path is None:
            return ToolResult(
                success=False,
                error=(
                    f"Model not found: {model_name}. Place the .onnx file in "
                    "assets/voices/, ~/.local/share/piper/, or ~/.piper/models/"
                ),
            )

        voice = PiperVoice.load(model_path)
        syn_config = SynthesisConfig(
            speaker_id=inputs.get("speaker_id", 0),
            length_scale=inputs.get("length_scale", 1.0),
        )
        sentence_silence = inputs.get("sentence_silence", 0.3)
        text = inputs["text"]

        with wave.open(str(output_path), "wb") as wav_file:
            wav_params_set = False
            for i, chunk in enumerate(voice.synthesize(text, syn_config)):
                if not wav_params_set:
                    wav_file.setframerate(chunk.sample_rate)
                    wav_file.setsampwidth(chunk.sample_width)
                    wav_file.setnchannels(chunk.sample_channels)
                    wav_params_set = True
                if i > 0:
                    silence_bytes = bytes(int(chunk.sample_rate * sentence_silence * 2))
                    wav_file.writeframes(silence_bytes)
                wav_file.writeframes(chunk.audio_int16_bytes)

        if not output_path.exists():
            return ToolResult(success=False, error=f"Output file was not created: {output_path}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model_name,
                "speaker_id": inputs.get("speaker_id", 0),
                "text_length": len(text),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=model_name,
        )
