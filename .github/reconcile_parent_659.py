#!/usr/bin/env python3
"""One-shot documentation reconciliation for stacked narration PR #669."""
from __future__ import annotations

from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one {label}; found {count}")
    return text.replace(old, new)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    value, count = re.subn(pattern, replacement, text, flags=re.S)
    if count != 1:
        raise SystemExit(f"Expected one {label}; found {count}")
    return value


voice_path = Path("docs/spoken-briefs/VOICE-PROFILE.md")
voice = voice_path.read_text(encoding="utf-8")
voice = sub_once(
    voice,
    r"A local profile cannot silently replace a checked-in revision\. Replacement requires:\n\n.*?New local profile IDs must not claim to supersede an unknown record\.",
    """A local profile can overlay a checked-in catalogue profile only when it carries:

- the same stable profile ID;
- a strictly higher integer revision than the checked-in profile;
- `supersedes_profile_sha256` equal to the exact checked-in catalogue profile hash.

This guard detects catalogue drift: a local overlay prepared for different checked-in profile bytes is refused. It is not a mutable registry compare-and-swap operation, a persisted local revision chain, or a concurrent-writer lock. Each resolution starts from the checked-in catalogue and then applies at most one local record per profile ID. Replacing the registry file is an external operator action; competing writers are not serialized by the resolver. Issue #671 tracks a genuine local CAS update boundary if that stronger property is needed.

New local profile IDs must not claim to supersede an unknown catalogue record.""",
    "voice registry section",
)
voice = replace_once(
    voice,
    "A local profile registry may change the profile binding under the compare-and-swap rules above.",
    "A local profile registry may overlay a checked-in profile under the catalogue-drift guard above.",
    "voice policy overlay sentence",
)
voice = replace_once(
    voice,
    "- the local revision names the exact checked-in/profile revision it supersedes.",
    "- the local overlay names the exact checked-in catalogue profile it replaces.",
    "voice promotion bullet",
)
voice = replace_once(
    voice,
    "canonical hashes, revision compare-and-swap, delivery binding,",
    "canonical hashes, catalogue-bound overlay validation, delivery binding,",
    "voice evidence claim",
)
voice = sub_once(
    voice,
    r"- that a custom producer adapter exists\.\n\nThose require local retained evidence and human listening\. Broader producer, audition, replacement, alignment, and dialogue tooling remains #28; transcript and pronunciation workflow remains #641\.",
    """- that a custom producer adapter exists;
- that local registry file writers are serialized or form a durable predecessor chain.

Those require local retained evidence and human listening. Broader producer, audition, replacement, alignment, and dialogue tooling remains #28; transcript and pronunciation workflow remains #641; stronger registry mutation semantics remain #671.""",
    "voice evidence boundary",
)
voice_path.write_text(voice, encoding="utf-8")

readme_path = Path("research/voice-profiles/README.md")
readme = readme_path.read_text(encoding="utf-8")
readme = sub_once(
    readme,
    r"## Local registry\n.*?(?=\n## )",
    """## Local catalogue overlay

Private or machine-specific records belong under an ignored `_voice_profiles/` directory. Supply a registry with `--profile-registry` or PowerShell `-ProfileRegistry`.

Overlaying a checked-in profile requires:

```json
{
  "id": "ember-brief-v1",
  "revision": 2,
  "supersedes_profile_sha256": "the exact checked-in catalogue profile hash"
}
```

The overlay must contain the complete strict profile schema. A hash for different checked-in catalogue bytes, unchanged revision, duplicate ID, unsupported field, malformed hash, filesystem path masquerading as an asset ID, or inconsistent acceptance state is rejected.

This is a catalogue-drift guard, not a mutable compare-and-swap registry. Resolution always starts from the checked-in catalogue and applies at most one local record per profile ID. The resolver does not retain local predecessor state or serialize competing file writers; issue #671 tracks that stronger mutation boundary.
""",
    "research local overlay section",
)
readme = readme.replace(
    "The normalized result is evidence for a later local profile revision.",
    "The normalized result is evidence for a later local catalogue overlay.",
)
readme_path.write_text(readme, encoding="utf-8")

plan_path = Path("docs/superpowers/plans/2026-09-19-narration-policy-hardening.md")
plan = plan_path.read_text(encoding="utf-8")
plan = replace_once(
    plan,
    "Keep PR #653's profile catalogue, local compare-and-swap registry, profile/delivery manifest binding, and pre-side-effect execution admission unchanged.",
    "Keep PR #653's profile catalogue, catalogue-bound local overlay, profile/delivery manifest binding, and pre-side-effect execution admission unchanged.",
    "plan parent constraint",
)
plan = replace_once(
    plan,
    "A local profile registry may change only the profile binding; it cannot redefine candidates, measurements, evaluation text, contrast pairing, or long-form requirements.",
    "A local profile registry may overlay only the profile binding from the checked-in catalogue; it cannot redefine candidates, measurements, evaluation text, contrast pairing, or long-form requirements, and it is not treated as durable mutable CAS state.",
    "plan local overlay constraint",
)
plan_path.write_text(plan, encoding="utf-8")
