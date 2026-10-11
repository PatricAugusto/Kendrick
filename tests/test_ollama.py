import asyncio
import json
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.request import Request

import pytest

from kendrick_bot.llm.ollama import OllamaClient, OllamaError


def test_ask_posts_question_and_returns_model_response() -> None:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(
        {"message": {"content": "Planeje as refeições da semana."}}
    ).encode()

    with patch("kendrick_bot.llm.ollama.urlopen", return_value=response) as urlopen:
        result = asyncio.run(
            OllamaClient("http://localhost:11434/", "llama3.2").ask(
                "Como planejar?"
            )
        )

    request = urlopen.call_args.args[0]
    assert isinstance(request, Request)
    assert request.full_url == "http://localhost:11434/api/chat"
    assert request.get_method() == "POST"
    body = json.loads(request.data)
    assert body["model"] == "llama3.2"
    assert body["stream"] is False
    assert body["messages"][-1] == {
        "role": "user",
        "content": "Como planejar?",
    }
    assert result == "Planeje as refeições da semana."


def test_ask_reports_connection_error() -> None:
    with patch(
        "kendrick_bot.llm.ollama.urlopen",
        side_effect=URLError("connection refused"),
    ):
        with pytest.raises(OllamaError, match="Não foi possível conectar"):
            asyncio.run(
                OllamaClient("http://localhost:11434", "llama3.2").ask("Dúvida")
            )


def test_ask_rejects_empty_or_malformed_model_response() -> None:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'{"message":{"content":"  "}}'

    with patch("kendrick_bot.llm.ollama.urlopen", return_value=response):
        with pytest.raises(OllamaError, match="resposta vazia"):
            asyncio.run(
                OllamaClient("http://localhost:11434", "llama3.2").ask("Dúvida")
            )
