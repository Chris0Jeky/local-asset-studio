# Share an allowance across edit revisions

New v2 edit handoffs can share one explicitly registered campaign allowance in
Studio's existing Production coordinator. Creating a receipt and preparing a
handoff remain offline. Registration records a cap with zero reservations;
staging uploads and prepares comparisons; explicit Start reserves their actual
stages. None of these earlier steps starts inference.

Choose a new campaign's cap and revision membership deliberately. An existing
campaign's ID and full receipt remain fixed. A repeated registration of the same
receipt returns the existing remaining budget; changing its cap or owner is
rejected. Creating a different receipt does not enroll it in Studio.

The following uses an example cap of three. It does not authorize a real run or
extend an existing pilot. Use the same receipt for every revision in the campaign:

```console
python scripts/character_edit_campaign.py create --workspace C:/AI/character-lab/EDIT_WORKSPACE --out campaign.json --budget-owner OWNER_LABEL --max-generation-attempts 3
python scripts/character_edit_bridge.py register-campaign --workspace C:/AI/character-lab/EDIT_WORKSPACE --campaign campaign.json
python scripts/character_edit_bridge.py campaign-status --workspace C:/AI/character-lab/EDIT_WORKSPACE --campaign campaign.json
python scripts/character_edit_bridge.py prepare --workspace C:/AI/character-lab/EDIT_WORKSPACE --plan plan.json --out handoff-revision-1 --seeds 11 22 --campaign campaign.json
python scripts/character_edit_bridge.py stage --workspace C:/AI/character-lab/EDIT_WORKSPACE --handoff handoff-revision-1/handoff.json
```

Use the existing [Studio bridge](STUDIO-BRIDGE.md) commands to inspect the staged
project and explicitly start, collect or compose it. If registration's response
is lost, use `campaign-status` with the retained receipt. If project creation or
Start is uncertain, preserve its journal and use the existing status/reconcile
path; a new campaign is not a recovery action.

## What the cap counts

Each campaign has a distinct opaque ID and a canonical receipt hash. Registered
budgets use `character-edit:<campaign_id>` in the existing Production database.
Each edit plan gets one deterministic project in that campaign, regardless of
display name or a changed seed list. Re-importing it is refused before replacing
the original project files.

Two two-stage revisions in a three-attempt campaign can both be prepared, but
only one can Start. Their reservation is shared, transactional and retained on
reopen, failure or an uncertain outcome. The per-handoff comparison bound still
applies: one to four seeds, with primary candidates and planned repair slots
fitting the handoff's cap of at most sixteen. The campaign cap can span several
revisions, up to sixty-four actual started stages.

`reserved_repairs` remains an edit-plan constraint. This slice does not reserve
unused repair slots globally or establish a new per-case repair allocator.
Successful generation, owner acceptance and rights review remain separate states.

## Integrity and compatibility

Local validation checks the raw bytes of the plan, campaign, source, canon, masks
and references. The server validates embedded JSON contracts and the actual
uploaded/Comfy-input reference bytes. It does not open arbitrary client workspace
paths. A canonical plan hash identifies its meaning; the raw file hash also
detects local serialization changes. Caller-provided hashes are integrity
evidence, not authentication of an owner decision.

Staging requires an existing matching registration. It never creates a missing
campaign budget. The registered receipt and allowance are checked again in the
same transaction that records the project. No existing budget or project is
migrated. Omitting `--campaign` retains the legacy v1 handoff behavior, and the
existing `character-study:<plan_sha256>` roots keep their prior reservations.

This addition has been exercised with synthetic HTTP/Production fixtures only.
No real campaign was registered or started, no existing pilot was extended, and
no runtime was restarted for this implementation. Issue #65 remains open for its
broader recovery, repair accounting, workstation and creative acceptance criteria.
