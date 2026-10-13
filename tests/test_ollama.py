import asyncio
import json
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.request import Request

import pytest

from kendrick_bot.llm.ollama import OllamaClient, OllamaError, PurchaseSuggestion


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


def test_suggest_purchases_requests_and_parses_structured_response() -> None:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(
        {
            "message": {
                "content": (
                    '{"items":[{"name":"tomates","quantity":"2.5","unit":"kg"},'
                    '{"name":"azeite","quantity":"1","unit":null}]}'
                )
            }
        }
    ).encode()

    with patch("kendrick_bot.llm.ollama.urlopen", return_value=response) as urlopen:
        result = asyncio.run(
            OllamaClient("http://localhost:11434", "llama3.2").suggest_purchases(
                "jantar para 4",
                "Despensa: vazia\nLista de compras: leite",
            )
        )

    request = urlopen.call_args.args[0]
    body = json.loads(request.data)
    assert "JSON válido" in body["messages"][0]["content"]
    assert "Despensa: vazia" in body["messages"][-1]["content"]
    assert "jantar para 4" in body["messages"][-1]["content"]
    assert result == [
        PurchaseSuggestion("tomates", Decimal("2.5"), "kg"),
        PurchaseSuggestion("azeite", Decimal("1"), None),
    ]


@pytest.mark.parametrize(
    "content",
    [
        "não é JSON",
        '{"items":[{"name":"arroz","quantity":"NaN","unit":"kg"}]}',
        '{"items":[{"name":"arroz","quantity":"-1","unit":"kg"}]}',
        '{"items":[{"name":"arroz","quantity":"1","unit":"kg/l"}]}',
        '{"items":[{"name":"arroz","quantity":"1","unit":"kg"},'
        '{"name":"ARROZ","quantity":"1","unit":"L"}]}',
    ],
)
def test_suggest_purchases_rejects_invalid_model_output(content: str) -> None:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(
        {"message": {"content": content}}
    ).encode()

    with patch("kendrick_bot.llm.ollama.urlopen", return_value=response):
        with pytest.raises(OllamaError):
            asyncio.run(
                OllamaClient("http://localhost:11434", "llama3.2").suggest_purchases(
                    "jantar",
                    "lista vazia",
                )
            )
