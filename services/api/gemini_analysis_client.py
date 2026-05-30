from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


_API_KEY_ENV_NAMES = (
    "AI_ANALYSIS_GEMINI_API_KEY",
    "CHAT_GEMINI_API_KEY",
    "GEMINI_API_KEY",
)


@dataclass
class AiAnalysisCitation:
    title: str
    url: str
    source: str | None = None
    published_at: str | None = None


@dataclass
class AiAnalysisResult:
    provider: str
    model: str
    content: str
    citations: list[AiAnalysisCitation] = field(default_factory=list)
    latency_ms: int = 0


class GeminiAnalysisClient:
    provider = "gemini"
    default_model = "gemini-2.5-flash"

    def __init__(self) -> None:
        self._api_key = self._read_first_env(_API_KEY_ENV_NAMES)
        self._temperature = float(os.getenv("AI_ANALYSIS_GEMINI_TEMPERATURE", "0.15") or 0.15)
        # 1800 truncaba el análisis: gemini-2.5-flash es "thinking" y consume
        # parte del budget razonando, y el prompt pide 6 secciones. 4096 da aire
        # para el razonamiento + un análisis completo sin cortarse.
        self._max_output_tokens = int(
            os.getenv("AI_ANALYSIS_GEMINI_MAX_OUTPUT_TOKENS", "4096") or 4096
        )
        self._sdk_configured = False

    @staticmethod
    def _read_first_env(names: tuple[str, ...]) -> str:
        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    def _sdk_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401
        except Exception:
            return False
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._sdk_available()

    def _ensure_sdk(self):
        import google.generativeai as genai  # type: ignore

        if not self._sdk_configured:
            genai.configure(api_key=self._api_key)
            self._sdk_configured = True
        return genai

    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> AiAnalysisResult:
        if not self._api_key:
            raise RuntimeError("Gemini no está configurado.")

        chosen_model = self.default_model
        genai = self._ensure_sdk()
        client = genai.GenerativeModel(
            model_name=chosen_model,
            system_instruction=system_prompt,
            generation_config={
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        )
        started = time.perf_counter()
        try:
            response = client.generate_content(
                user_prompt,
                request_options={"timeout": 25},
            )
        except Exception as exc:
            message = str(exc)
            if "ResourceExhausted" in message or "quota" in message.lower():
                raise RuntimeError(
                    f"{chosen_model} no está disponible para esta API key o cuota actual. "
                    "Necesitás habilitar billing/cuota para ese modelo o cambiar a otro."
                ) from exc
            raise RuntimeError(f"No se pudo completar el análisis con Gemini: {message}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = ""
        try:
            text = (getattr(response, "text", None) or "").strip()
        except Exception:
            text = ""
        if not text:
            try:
                candidates = getattr(response, "candidates", None) or []
                for candidate in candidates:
                    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
                    joined = "".join(getattr(part, "text", "") or "" for part in parts).strip()
                    if joined:
                        text = joined
                        break
            except Exception:
                text = ""
        if not text:
            text = "No se pudo generar una respuesta útil."

        return AiAnalysisResult(
            provider=self.provider,
            model=chosen_model,
            content=text,
            citations=[],
            latency_ms=latency_ms,
        )
