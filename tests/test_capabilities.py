from app.assistant.answer_executor import AnswerExecutor
from app.assistant.capabilities import format_capability_catalog, list_capability_items
from app.tools import list_tools


class _StubClient:
    def __init__(self, response: str = "Drafted capability summary.") -> None:
        self.response = response
        self.messages = None

    def complete(self, messages) -> str:
        self.messages = messages
        return self.response


def test_list_capability_items_includes_registered_tools() -> None:
    tool_names = {tool.name for tool in list_tools()}
    capability_names = {item.name for item in list_capability_items()}

    assert tool_names.issubset(capability_names)
    assert "conversation" in capability_names
    assert "memory_wipe" in capability_names


def test_format_capability_catalog_lists_tool_descriptions() -> None:
    catalog = format_capability_catalog()

    assert "Available capabilities (grouped):" in catalog
    assert "Notes and memory:" in catalog
    assert "check_health:" in catalog
    assert "create_pull_request:" in catalog


def test_draft_capabilities_uses_tool_catalog_in_prompt() -> None:
    client = _StubClient()
    executor = AnswerExecutor()

    source = executor.draft_capabilities(
        client=client,
        message="What can you do?",
        conversation_id="default",
    )

    assert source.facts == "Drafted capability summary."
    assert client.messages is not None
    assert "Available capabilities (grouped):" in client.messages[-1]["content"]
    assert "run_python:" in client.messages[-1]["content"]
    assert "User question: What can you do?" in client.messages[-1]["content"]
