"""Bounded durable receipts for large-job preparation."""
from __future__ import annotations

import copy
import json
from typing import Any

from large_job_prep_common import (
    JOURNAL_SCHEMA, MAX_JOURNAL_BYTES, MAX_RECORDS, MAX_RECEIPT_BYTES,
    PreparationError, _canonical, _digest,
)


class JournalMixin:
    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": JOURNAL_SCHEMA, "records": []}
        except (OSError, json.JSONDecodeError) as exc:
            raise PreparationError("Large-job preparation journal is unavailable or corrupt") from exc
        if not isinstance(value, dict) or value.get("schema") != JOURNAL_SCHEMA:
            raise PreparationError("Large-job preparation journal schema is invalid")
        records = value.get("records")
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise PreparationError("Large-job preparation journal retention is invalid")
        seen = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("request_id"), str):
                raise PreparationError("Large-job preparation journal contains an invalid record")
            if record["request_id"] in seen:
                raise PreparationError("Large-job preparation journal contains duplicate request identities")
            seen.add(record["request_id"])
        _canonical(value, MAX_JOURNAL_BYTES)
        return value

    def _persist(self, journal: dict[str, Any], receipt: dict[str, Any]) -> None:
        receipt.pop("replayed", None)
        receipt.pop("receipt_sha256", None)
        receipt["receipt_sha256"] = _digest(receipt)
        records = journal["records"]
        for index, existing in enumerate(records):
            if existing.get("request_id") == receipt["request_id"]:
                records[index] = copy.deepcopy(receipt)
                break
        else:
            if len(records) >= MAX_RECORDS:
                raise PreparationError("Large-job preparation receipt retention is full")
            records.append(copy.deepcopy(receipt))
        _canonical(receipt, MAX_RECEIPT_BYTES)
        _canonical(journal, MAX_JOURNAL_BYTES)
        writer = getattr(self.studio, "_write_json_atomic", None)
        if callable(writer):
            writer(self.path, journal)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(journal, sort_keys=True), encoding="utf-8")
            temporary.replace(self.path)

    def _finish(self, journal: dict[str, Any], receipt: dict[str, Any], *, state: str,
                decision: str, ready: bool, reason: str, phase: str) -> dict[str, Any]:
        receipt.update(
            state=state,
            phase=phase,
            finished_at=self.clock(),
            final={
                "decision": decision,
                "ready": ready,
                "reason": reason[:500],
                "generation_submitted": False,
            },
        )
        self._persist(journal, receipt)
        return copy.deepcopy(receipt)
    def _record_action(self, journal: dict[str, Any], receipt: dict[str, Any], action: dict[str, Any]) -> None:
        receipt.setdefault("actions", []).append(action)
        self._persist(journal, receipt)
