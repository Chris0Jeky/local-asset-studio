"""Offline, hash-bound identity receipt for a character edit campaign.

Creation only writes local metadata. Campaign registration, HTTP, SQLite,
native applications, generation and enrollment belong to later explicit steps.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import uuid

from scripts import character_edit_bridge_io as io


KEYS = {"schema_version", "kind", "campaign_id", "budget_owner", "max_generation_attempts", "campaign_sha256"}


def _body(value):
    return {key: item for key, item in value.items() if key != "campaign_sha256"}


def validate(value):
    """Return a detached, canonical campaign receipt or reject every mismatch."""
    io.require(isinstance(value, dict) and set(value) == KEYS, "Invalid campaign receipt keys")
    io.require(type(value["schema_version"]) is int and value["schema_version"] == 1, "Unsupported campaign receipt version")
    io.require(value["kind"] == "character_edit_campaign", "Invalid campaign receipt kind")
    io.require(isinstance(value["campaign_id"], str) and io.PROJECT.fullmatch(value["campaign_id"]), "Invalid campaign ID")
    owner = value["budget_owner"]
    io.require(isinstance(owner, str) and owner == owner.strip() and 0 < len(owner) <= 120, "Invalid budget owner")
    cap = value["max_generation_attempts"]
    io.require(type(cap) is int and 1 <= cap <= 64, "Invalid generation attempt cap")
    io.require(isinstance(value["campaign_sha256"], str) and io.HEX.fullmatch(value["campaign_sha256"])
               and value["campaign_sha256"] == io.digest(io.canonical(_body(value))), "Campaign receipt hash mismatch")
    return copy.deepcopy(value)


def create(budget_owner, max_generation_attempts, *, campaign_id=None):
    """Create one validated receipt, preserving an explicitly supplied ID."""
    value = {"schema_version": 1, "kind": "character_edit_campaign",
             "campaign_id": uuid.uuid4().hex if campaign_id is None else campaign_id,
             "budget_owner": budget_owner, "max_generation_attempts": max_generation_attempts}
    value["campaign_sha256"] = io.digest(io.canonical(value))
    return validate(value)


def write(workspace, output, budget_owner, max_generation_attempts, *, campaign_id=None):
    """Exclusively save a new campaign receipt below the selected workspace."""
    root = Path(workspace).resolve(strict=True)
    target = io.local(root, output, exists=False)
    value = create(budget_owner, max_generation_attempts, campaign_id=campaign_id)
    io.save_new(target, value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create")
    create_parser.add_argument("--workspace", type=Path, required=True)
    create_parser.add_argument("--out", required=True)
    create_parser.add_argument("--budget-owner", required=True)
    create_parser.add_argument("--max-generation-attempts", type=int, required=True)
    create_parser.add_argument("--campaign-id")
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--workspace", type=Path, required=True)
    inspect_parser.add_argument("--campaign", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            value = write(args.workspace, args.out, args.budget_owner, args.max_generation_attempts,
                          campaign_id=args.campaign_id)
        else:
            root = Path(args.workspace).resolve(strict=True)
            value = validate(io.read(io.local(root, args.campaign)))
        print(io.canonical(value).decode("utf-8"))
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        parser.exit(2, "character-edit-campaign: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
