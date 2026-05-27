"""End-to-end classification service.

Two entry points:

- :meth:`classify_with_raw` — accepts an already-produced raw output string
  (used by ``--mock-output`` and by tests; fully offline).
- :meth:`classify_item` — issues a live Ollama call via the bound
  :class:`OllamaChatClient`, then dispatches the same downstream pipeline.

Both paths share: validation -> routing -> persistence. Validation failures
are surfaced as exceptions; no decision is persisted on rejection.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.construction.store import ConstructionStore

from .client import OllamaChatClient
from .models import (
    ClassificationDecision,
    ModelRoutingConfig,
    ModelTask,
)
from .router import ClassificationRouter
from .validator import parse_and_validate


class ClassificationService:
    def __init__(
        self,
        *,
        config: ModelRoutingConfig,
        router: ClassificationRouter,
        store: ConstructionStore,
        client: OllamaChatClient | None = None,
    ) -> None:
        self._config = config
        self._router = router
        self._store = store
        self._client = client

    def classify_with_raw(
        self,
        *,
        raw_output: str,
        source_key: str,
        item_id: str,
        project_key: str | None,
        model_task: ModelTask,
        model_name: str,
        inventory_item: dict[str, Any] | None = None,
    ) -> ClassificationDecision:
        classification = parse_and_validate(raw_output)
        # Guardrail: the model is told the item_id in the prompt and must echo
        # it back. If it doesn't match, treat as a routing override (force
        # review) rather than silently trusting the wrong item.
        forced_review_reason: str | None = None
        if classification.item_id != item_id:
            forced_review_reason = f"item_id_mismatch:{classification.item_id!r}"

        decision = self._router.decide(
            classification=classification,
            source_key=source_key,
            item_id=item_id,
            project_key=project_key,
            model_name=model_name,
            model_task=model_task,
            raw_output=raw_output,
            inventory_item=inventory_item,
        )
        if forced_review_reason is not None:
            decision = decision.model_copy(update={
                "status": "review",
                "routing_reason": (
                    decision.routing_reason + ";" + forced_review_reason
                    if decision.routing_reason != "model_accepted"
                    else forced_review_reason
                ),
            })
        self._store.record_model_decision(decision)
        return decision

    def classify_item(
        self,
        *,
        source_key: str,
        item_id: str,
        project_key: str | None,
        model_task: ModelTask,
        inventory_item: dict[str, Any],
    ) -> ClassificationDecision:
        if self._client is None:
            raise RuntimeError(
                "classify_item requires a bound OllamaChatClient. "
                "Use classify_with_raw for offline testing/proof."
            )
        task_routing = self._config.task_for(model_task)
        prompt = self._build_prompt(
            item_id=item_id,
            inventory_item=inventory_item,
            system=task_routing.system_prompt,
        )
        raw_output = self._client.generate_json(
            system=task_routing.system_prompt, prompt=prompt,
        )
        return self.classify_with_raw(
            raw_output=raw_output,
            source_key=source_key,
            item_id=item_id,
            project_key=project_key,
            model_task=model_task,
            model_name=task_routing.model,
            inventory_item=inventory_item,
        )

    @staticmethod
    def _build_prompt(
        *, item_id: str, inventory_item: dict[str, Any], system: str,
    ) -> str:
        # Metadata only. Document body / content / text never appears.
        name = inventory_item.get("name") or "(unknown)"
        parent_path = inventory_item.get("parent_path") or "(unknown)"
        return (
            f"Classify the following construction document by metadata only.\n"
            f"item_id: {item_id}\n"
            f"name: {name}\n"
            f"parent_path: {parent_path}\n"
            "Respond with a single JSON object matching the required schema."
        )
