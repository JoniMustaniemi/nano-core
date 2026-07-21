from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import tool_result_source


class ToolResultSummarizer:
    """
    Backward-compatible wrapper around ResponseComposer.
    """

    def __init__(self, *, composer: ResponseComposer | None = None) -> None:
        """
        Initialize the summarizer.

        Args:
            composer: Response composer used for summarization.
        """
        self.composer = composer or ResponseComposer()

    def summarize(
        self,
        *,
        client,
        user_message: str,
        tool_name: str,
        tool_result: str,
    ) -> str:
        """
        Summarize the requested operation.

        Args:
            client: LLM client used to generate responses.
            user_message: User message value.
            tool_name: Registered tool name.
            tool_result: Serialized tool result to summarize.

        Returns:
            Generated or formatted string value.
        """
        source = tool_result_source(
            user_message=user_message,
            facts=tool_result,
            tool_name=tool_name,
        )
        return self.composer.compose(client, source)
