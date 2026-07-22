from __future__ import annotations

from typing import Protocol

from app.assistant.response_source import ResponseSource
from app.llm.protocol import LLMClient
from app.proactive.types import ProactiveOffer


class ProactiveDeliveryHandler(Protocol):
  def deliver(
    self,
    *,
    offer: ProactiveOffer,
    client: LLMClient,
    conversation_id: str,
  ) -> ResponseSource: ...


class ProactiveDeliveryRegistry:
  def __init__(self) -> None:
    self._handlers: dict[str, ProactiveDeliveryHandler] = {}

  def register(self, kind: str, handler: ProactiveDeliveryHandler) -> None:
    self._handlers[kind] = handler

  def deliver(
    self,
    *,
    offer: ProactiveOffer,
    client: LLMClient,
    conversation_id: str,
  ) -> ResponseSource:
    handler = self._handlers.get(offer.kind)
    if handler is None:
      from app.assistant.response_source import answer_source

      return answer_source(
        user_message="proactive offer",
        facts=offer.summary,
        conversation_id=conversation_id,
      )
    return handler.deliver(offer=offer, client=client, conversation_id=conversation_id)


delivery_registry = ProactiveDeliveryRegistry()


def _register_builtin_handlers() -> None:
  from app.proactive.deliveries.self_improvement import register_delivery_handlers

  register_delivery_handlers(delivery_registry)


_register_builtin_handlers()
