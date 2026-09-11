---
name: model-aware-creative-intent
description: Clarify a creative brief, inspect reference metadata, obtain optional local text/vision proposals, compile model-specific fields and hand off a reviewed plan without silently changing intent or generation settings.
---

Read `docs/prompt-studio/HANDOFF.md`, model profiles and current Studio state. Preserve queues, models and existing user work.

Start from a CreativeIntent, not a rewritten prompt string. Separate brief, subject/action/style/motion, exact speech/lyrics, typed reference contributions, constraints and locks. Unknown attributes stay unknown. Ask only the question that materially affects the next step; reuse supplied decisions.

Inspect embedded recipe claims before using vision reconstruction. Never execute imported workflow metadata. Pixels do not identify a unique original prompt, seed or checkpoint. Use local helpers as proposal generators, validate the result and accept changes explicitly. Respect locked fields; pose/style references do not authorise a new identity.

Use `scripts/studio_prompt.py profiles`, `compile`, `inspect-png`, `request-helper`, `run-helper`, `apply`, `bind` and `experiment` according to their contracts. `request-helper` does not infer. `run-helper` performs one bounded helper call only; it requires an already installed local model and an idle/resource decision. The per-workspace lock is not a global GPU scheduler.

Review model-specific outputs and unresolved fields. Do not insert negative prompts into an unsupported backend, fabricate tags/triggers, put directions in spoken dialogue, or pretend image-only3D accepts text. Exact masks, geometry, alpha and motion contracts belong in appropriate control/finishing stages.

A compiled artifact is a proposal. Existing Studio submission guards, actual node validation and runtime blocks remain authoritative. Never submit on page load or repeat an uncertain job. Keep an unchanged benchmark baseline and judge useful outputs and cleanup, not prompt verbosity.
