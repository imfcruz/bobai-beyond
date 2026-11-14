"""
Abstração de integração com LLM — agnóstica de provedor.

Suporta: mock determinístico, IBM Bob Shell e IBM Watsonx.
Implementa: timeout, retry com backoff, model tracking, isolamento de erros.

SEGURANÇA:
  - Credenciais nunca aparecem em logs ou respostas.
  - Saída da LLM é sempre validada antes de uso.
  - Erros resultam em fallback, nunca em falha silenciosa.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Tempo máximo de espera por resposta da LLM
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_RETRIES = 2


# ── Interface base ────────────────────────────────────────────────────────────

class BaseLLMClient(abc.ABC):
    """Contrato que todos os provedores de LLM devem implementar."""

    @abc.abstractmethod
    async def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Envia um prompt e retorna a resposta em texto."""
        ...

    @abc.abstractmethod
    async def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Envia um prompt e retorna JSON parseado e validado."""
        ...

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def model_identifier(self) -> str:
        """Identificador público do modelo (sem credenciais)."""
        ...


# ── Mock (RULES_MODE — padrão para desenvolvimento e testes) ──────────────────

class MockLLMClient(BaseLLMClient):
    """
    Cliente mock para desenvolvimento e testes.
    Opera em RULES_MODE — respostas determinísticas, sem chamadas externas.
    NUNCA deve ser apresentado como IA generativa real.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_identifier(self) -> str:
        return "rules/mock-v1"

    async def complete(self, prompt: str, system_prompt: str = "") -> str:
        logger.debug("MockLLM complete called", prompt_len=len(prompt))
        return (
            "Análise baseada em regras (RULES_MODE). "
            "Este resultado não é gerado por um modelo de linguagem."
        )

    async def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        logger.debug("MockLLM complete_json called", prompt_len=len(prompt))
        return {
            "risk_level": "LOW",
            "confidence": 0.70,
            "detected_signals": [],
            "evidence": ["Análise baseada em regras determinísticas (RULES_MODE)"],
            "explanation": "Resultado de RULES_MODE — sem modelo de linguagem.",
            "recommended_action": "APPROVE",
        }


# ── IBM Bob Shell ────────────────────────────────────────────────────────────

class BobShellLLMClient(BaseLLMClient):
    """Cliente para automação documentada do IBM Bob via ``bob run``.

    O Bob seleciona o modelo conforme a instância e o time associados à chave
    de inferência, por isso este provedor não exige ``LLM_MODEL``. A execução é
    isolada em um workspace sem arquivos do projeto e limita ferramentas,
    turnos e custo para que o processo se comporte como inferência textual.
    """

    def __init__(self):
        if not settings.BOB_API_KEY:
            raise ValueError(
                "BOB_API_KEY não configurada. Cole a chave de inferência no "
                "backend/.env ou use LLM_PROVIDER=mock."
            )
        executable = shutil.which(settings.BOB_SHELL_COMMAND)
        if executable is None:
            raise RuntimeError(
                "IBM Bob Shell não encontrado. Instale o comando 'bob' conforme "
                "a documentação oficial antes de usar LLM_PROVIDER=bob."
            )
        self._executable = executable

    @property
    def provider_name(self) -> str:
        return "bob"

    @property
    def model_identifier(self) -> str:
        return "ibm-bob/team-inference"

    async def complete(self, prompt: str, system_prompt: str = "") -> str:
        runtime_dir = Path(__file__).resolve().parents[2] / "data" / "bob-runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        combined_prompt = (
            "Você atua somente como classificador de risco do protótipo BobIA. "
            "Não leia nem altere arquivos e não execute ferramentas. "
            "Responda exclusivamente ao pedido a seguir.\n\n"
            f"INSTRUÇÕES DO SISTEMA:\n{system_prompt}\n\n"
            f"DADOS PARA ANÁLISE:\n{prompt}"
        )

        command = [
            self._executable,
            "run",
            "--format", "json",
            "--mode", "ask",
            "--max-cost", str(settings.BOB_MAX_COST),
            "--max-turns", "1",
            "--disable-mcp",
            "--disable-subagents",
            "--disable-tool-groups", "execute,mcp",
            "--workspace", str(runtime_dir),
            "--trust",
            "--accept-license",
        ]
        if settings.BOB_TEAM_ID:
            command.extend(["--team-id", settings.BOB_TEAM_ID])
        command.append(combined_prompt)

        async def _call() -> str:
            process_env = os.environ.copy()
            process_env["BOB_API_KEY"] = settings.BOB_API_KEY
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=runtime_dir,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                error_text = stderr.decode("utf-8", errors="replace").casefold()
                if "budget exceeded" in error_text or "budget allowance" in error_text:
                    raise RuntimeError("IBM Bob sem Bobcoins disponíveis para inferência.")
                if "unauthorized" in error_text or "api key" in error_text:
                    raise RuntimeError("IBM Bob recusou a chave de inferência.")
                raise RuntimeError("IBM Bob Shell encerrou a inferência com erro.")

            try:
                result = json.loads(stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("IBM Bob Shell retornou JSON inválido.") from exc

            if result.get("status") != "success":
                raise RuntimeError("IBM Bob Shell não concluiu a inferência.")
            message = result.get("last_message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("IBM Bob Shell retornou uma resposta vazia.")
            return message

        return await _with_retry(
            _call,
            max_retries=0,
            timeout_s=settings.BOB_TIMEOUT_SECONDS,
            provider=self.provider_name,
        )

    async def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        raw = await self.complete(prompt, system_prompt)
        start = raw.find("{")
        if start == -1:
            raise ValueError(f"Resposta IBM Bob sem JSON estruturado: {raw[:100]}")

        depth = 0
        for index, char in enumerate(raw[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(raw[start:index + 1])
        raise ValueError(f"JSON incompleto na resposta IBM Bob: {raw[:200]}")


# ── Utilitário de retry com backoff ──────────────────────────────────────────

async def _with_retry(
    coro_factory,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    provider: str = "unknown",
) -> Any:
    """
    Executa uma coroutine com timeout e retry exponencial.
    Registra cada tentativa sem expor credenciais.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout_s)
        except TimeoutError as exc:
            last_exc = exc
            logger.warning(
                "LLM timeout", provider=provider, attempt=attempt,
                timeout_s=timeout_s,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "LLM call failed", provider=provider, attempt=attempt,
                error=type(exc).__name__,
                # deliberadamente não logamos str(exc) para evitar vazar credenciais
            )
        if attempt <= max_retries:
            await asyncio.sleep(0.5 * attempt)  # backoff simples
    raise last_exc or RuntimeError(f"LLM {provider}: all retries exhausted")


# ── Watsonx ───────────────────────────────────────────────────────────────────

class WatsonxLLMClient(BaseLLMClient):
    """
    Cliente IBM Watsonx (requer ibm-watsonx-ai e credenciais válidas).
    Configure LLM_PROVIDER=watsonx, LLM_API_KEY e WATSONX_PROJECT_ID no .env.
    """

    def __init__(self):
        if not settings.LLM_API_KEY or not settings.WATSONX_PROJECT_ID:
            raise ValueError(
                "LLM_API_KEY e WATSONX_PROJECT_ID necessários. "
                "Configure no .env ou use LLM_PROVIDER=mock."
            )
        try:
            from ibm_watsonx_ai import APIClient  # noqa: F401
        except ImportError as e:
            raise ImportError("Instale: pip install ibm-watsonx-ai") from e
        self._model = settings.LLM_MODEL or "ibm/granite-13b-chat-v2"
        self._project_id = settings.WATSONX_PROJECT_ID
        self._region = settings.WATSONX_REGION or "us-south"

    @property
    def provider_name(self) -> str:
        return "watsonx"

    @property
    def model_identifier(self) -> str:
        return f"watsonx/{self._model}"

    async def complete(self, prompt: str, system_prompt: str = "") -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        async def _call():
            # SDK síncrono — executa em thread pool separado para não bloquear o event loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_complete, full_prompt)

        return await _with_retry(_call, provider=self.provider_name)

    def _sync_complete(self, prompt: str) -> str:
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

        credentials = {
            "url": f"https://{self._region}.ml.cloud.ibm.com",
            "apikey": settings.LLM_API_KEY,
        }
        model = ModelInference(
            model_id=self._model,
            credentials=credentials,
            project_id=self._project_id,
            params={
                GenParams.MAX_NEW_TOKENS: settings.LLM_MAX_TOKENS,
                GenParams.TEMPERATURE: settings.LLM_TEMPERATURE,
            },
        )
        response = model.generate_text(prompt=prompt)
        return response

    async def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        raw = await self.complete(prompt, system_prompt)
        if not raw or not raw.strip():
            raise ValueError("Resposta Watsonx vazia")
        start = raw.find("{")
        if start == -1:
            raise ValueError(f"Resposta Watsonx sem JSON: {raw[:100]}")
        # Extrai o primeiro objeto JSON balanceado (ignora repetições do modelo)
        depth = 0
        end = -1
        for i, ch in enumerate(raw[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            raise ValueError(f"JSON incompleto na resposta Watsonx: {raw[:200]}")
        return json.loads(raw[start:end])


# ── Factory ───────────────────────────────────────────────────────────────────

class LLMClientFactory:
    """Instancia o cliente correto de acordo com LLM_PROVIDER."""

    _registry: dict[str, type[BaseLLMClient]] = {
        "mock": MockLLMClient,
        "bob": BobShellLLMClient,
        "watsonx": WatsonxLLMClient,
    }

    @classmethod
    def create(cls, provider: str | None = None) -> BaseLLMClient:
        provider = provider or settings.LLM_PROVIDER
        klass = cls._registry.get(provider)
        if klass is None:
            raise ValueError(
                f"LLM provider '{provider}' desconhecido. "
                f"Opções: {list(cls._registry.keys())}"
            )
        instance = klass()
        logger.info(
            "LLM client created",
            provider=provider,
            model=instance.model_identifier,
            # nunca logamos API keys ou project IDs
        )
        return instance

    @classmethod
    def register(cls, name: str, klass: type[BaseLLMClient]) -> None:
        """Permite registrar provedores customizados."""
        cls._registry[name] = klass


# ── Singleton global ──────────────────────────────────────────────────────────

_llm_client: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    """Dependency injection: retorna o cliente LLM configurado."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClientFactory.create()
    return _llm_client


def reset_llm_client() -> None:
    """Reseta o singleton — usado em testes."""
    global _llm_client
    _llm_client = None
