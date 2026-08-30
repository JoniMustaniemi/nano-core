from __future__ import annotations

from app.assistant.service import AssistantService
from app.runtime.activity import activity
from app.voice.output import get_voice_output
from app.voice.protocol import VoiceOutput
from app.voice.service import VoiceUnavailableError


class VoiceCommandService:
    def __init__(
        self,
        *,
        assistant: AssistantService | None = None,
        voice_output: VoiceOutput | None = None,
    ) -> None:
        self.assistant = assistant or AssistantService()
        self.voice_output = voice_output or get_voice_output()

    def handle_wake(self) -> None:
        response = self.assistant.wake_response()
        activity.log(title=response.content, detail=response.content, source="assistant.wake")
        try:
            self.voice_output.announce(response.content)
        except VoiceUnavailableError:
            pass

    def handle_command(self, message: str) -> None:
        response = self.assistant.respond(message, mode="agent")
        activity.log(title=response.content, detail=response.content, source="assistant.chat")
        if response.speak:
            try:
                self.voice_output.announce(response.content)
            except VoiceUnavailableError:
                pass
