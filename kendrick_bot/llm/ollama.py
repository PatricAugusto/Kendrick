import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when Ollama cannot provide a usable response."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def ask(self, question: str) -> str:
        return await asyncio.to_thread(self._ask_sync, question)

    def _ask_sync(self, question: str) -> str:
        request_body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Você é Kendrick, um assistente de compras domésticas. "
                        "Responda em português brasileiro, com clareza e "
                        "concisão. Ajude com planejamento de compras, "
                        "organização da despensa, comparação de critérios e "
                        "dicas práticas. Você não tem acesso à lista nem ao "
                        "estoque do usuário e não pode alterá-los. Não afirme "
                        "que fez compras ou mudanças; explique que o usuário "
                        "deve usar os comandos do bot para isso. Se não souber "
                        "algo ou a pergunta fugir desse tema, diga isso com "
                        "transparência."
                    ),
                },
                {"role": "user", "content": question},
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            raise OllamaError(
                f"Ollama respondeu com erro HTTP {error.code}."
            ) from None
        except (TimeoutError, URLError, OSError) as error:
            raise OllamaError(
                f"Não foi possível conectar ao Ollama: {error}."
            ) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise OllamaError("Ollama retornou uma resposta JSON inválida.") from None

        if not isinstance(payload, dict):
            raise OllamaError("Ollama retornou uma resposta inesperada.")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaError("Ollama não retornou uma mensagem.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama retornou uma resposta vazia.")
        return content.strip()
