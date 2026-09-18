#!/usr/bin/env python3
"""Temporary branch-only patcher for the #562 source-authentication correction."""
from __future__ import annotations

from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement, found {count}")
    return text.replace(old, new)


def patch_module() -> None:
    path = Path("studio_prompt/adult_illustration_prompt_membership.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from .adult_illustration_taxonomy import _validate_identity\n",
        "from .adult_illustration_taxonomy import (\n"
        "    _validate_identity,\n"
        "    validate_taxonomy_index,\n"
        ")\n",
        "taxonomy validator import",
    )
    text = replace_once(
        text,
        """    taxonomy_index: Any,
    root: Path | str = ".",
) -> dict[str, Any]:
    \"\"\"Inspect original compiler terms against one strict saved taxonomy index.\"\"\"""",
        """    taxonomy_index: Any,
    taxonomy_source: bytes,
    root: Path | str = ".",
) -> dict[str, Any]:
    \"\"\"Inspect terms only after exact taxonomy-source reconstruction.\"\"\"""",
        "inspection signature",
    )
    text = replace_once(
        text,
        """    index = _validated_index(taxonomy_index, root)
    _require_compatible(compiled, index)""",
        """    index = _validated_index(taxonomy_index, root)
    index = validate_taxonomy_index(index, taxonomy_source, root)
    _require_compatible(compiled, index)""",
        "inspection validation call",
    )
    text = replace_once(
        text,
        '            "source_revalidated": False,\n',
        '            "source_revalidated": True,\n',
        "source revalidation flag",
    )
    text = replace_once(
        text,
        """            \"The saved index content identity and current source/review contracts \"
            \"were validated, but exact source bytes were not rebuilt; \"
            \"source_revalidated remains false.\",""",
        """            \"The saved index was rebuilt from exact retained source bytes and \"
            \"the current review contract before source membership was classified.\",""",
        "source evidence limit",
    )
    text = replace_once(
        text,
        """    taxonomy_index: Any,
    root: Path | str = ".",
) -> dict[str, Any]:
    \"\"\"Recompute a retained report so changed derived evidence fails closed.\"\"\"""",
        """    taxonomy_index: Any,
    taxonomy_source: bytes,
    root: Path | str = ".",
) -> dict[str, Any]:
    \"\"\"Recompute a retained report so changed derived evidence fails closed.\"\"\"""",
        "report validation signature",
    )
    text = replace_once(
        text,
        """    expected = inspect_prompt_membership(
        compiled_prompt, source_projection, taxonomy_index, root
    )""",
        """    expected = inspect_prompt_membership(
        compiled_prompt,
        source_projection,
        taxonomy_index,
        taxonomy_source,
        root,
    )""",
        "report validation call",
    )
    path.write_text(text, encoding="utf-8")


def patch_cli() -> None:
    path = Path("scripts/studio_adult_illustration_prompt.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from studio_prompt.adult_illustration_prompt_projection import (  # noqa: E402\n",
        "from studio_prompt.adult_illustration_taxonomy_contracts import load_taxonomy_contracts  # noqa: E402\n"
        "from studio_prompt.adult_illustration_prompt_projection import (  # noqa: E402\n",
        "contract loader import",
    )
    text = replace_once(
        text,
        """def _read_json(path: str | Path, *, limit: int = DOCUMENT_LIMIT) -> Any:
    with Path(path).open(\"rb\") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f\"JSON exceeds {limit} byte limit\")
    try:""",
        """def _read_bounded(path: str | Path, limit: int, label: str) -> bytes:
    with Path(path).open(\"rb\") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f\"{label} exceeds {limit} byte limit\")
    return raw


def _read_json(path: str | Path, *, limit: int = DOCUMENT_LIMIT) -> Any:
    raw = _read_bounded(path, limit, \"JSON\")
    try:""",
        "bounded reader",
    )
    text = replace_once(
        text,
        '    membership.add_argument("--taxonomy-index", required=True)\n',
        '    membership.add_argument("--taxonomy-index", required=True)\n'
        '    membership.add_argument("--taxonomy-source", required=True)\n',
        "taxonomy source argument",
    )
    text = replace_once(
        text,
        """            taxonomy_index = _read_json(
                args.taxonomy_index, limit=TAXONOMY_INDEX_LIMIT
            )
            value = inspect_prompt_membership(
                compiled, source, taxonomy_index, args.repo_root
            )""",
        """            taxonomy_index = _read_json(
                args.taxonomy_index, limit=TAXONOMY_INDEX_LIMIT
            )
            contracts = load_taxonomy_contracts(args.repo_root)
            taxonomy_source = _read_bounded(
                args.taxonomy_source,
                contracts[\"source\"][\"bounds\"][\"max_source_bytes\"],
                \"Taxonomy source\",
            )
            value = inspect_prompt_membership(
                compiled,
                source,
                taxonomy_index,
                taxonomy_source,
                args.repo_root,
            )""",
        "CLI inspection call",
    )
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = Path("tests/test_adult_illustration_prompt_membership.py")
    text = path.read_text(encoding="utf-8")
    occurrences = text.count("projection, compiled, index = write_fixture(root)")
    if occurrences < 1:
        raise SystemExit("fixture destructuring: expected at least one replacement")
    text = text.replace(
        "projection, compiled, index = write_fixture(root)",
        "projection, compiled, index, taxonomy_source = write_fixture(root)",
    )
    text = replace_once(
        text,
        "    return projection, compiled, index\n",
        "    return projection, compiled, index, source\n",
        "fixture return",
    )
    replacements = {
        "inspect_prompt_membership(compiled, projection, index, root)":
            "inspect_prompt_membership(compiled, projection, index, taxonomy_source, root)",
        "inspect_prompt_membership(compiled, projection, stale, root)":
            "inspect_prompt_membership(compiled, projection, stale, taxonomy_source, root)",
        "inspect_prompt_membership(compiled, projection, changed, root)":
            "inspect_prompt_membership(compiled, projection, changed, taxonomy_source, root)",
        "inspect_prompt_membership(compiled, projection, malformed, root)":
            "inspect_prompt_membership(compiled, projection, malformed, taxonomy_source, root)",
        "inspect_prompt_membership(compiled, changed, index, root)":
            "inspect_prompt_membership(compiled, changed, index, taxonomy_source, root)",
        "validate_prompt_membership_report(\n                    first, compiled, projection, index, root\n                )":
            "validate_prompt_membership_report(\n                    first, compiled, projection, index, taxonomy_source, root\n                )",
        "validate_prompt_membership_report(\n                    changed, compiled, projection, index, root\n                )":
            "validate_prompt_membership_report(\n                    changed, compiled, projection, index, taxonomy_source, root\n                )",
    }
    for old, new in replacements.items():
        if old not in text:
            raise SystemExit(f"test call replacement missing: {old[:80]!r}")
        text = text.replace(old, new)
    text = replace_once(
        text,
        """                copy.deepcopy(index),
                root,
            )""",
        """                copy.deepcopy(index),
                taxonomy_source,
                root,
            )""",
        "detached deterministic inspection",
    )
    text = replace_once(
        text,
        """                report = inspect_prompt_membership(
                    compiled, projection, index, root
                )""",
        """                report = inspect_prompt_membership(
                    compiled,
                    projection,
                    index,
                    taxonomy_source,
                    root,
                )""",
        "runtime side-effect inspection",
    )
    text = replace_once(
        text,
        '        self.assertFalse(report["taxonomy"]["source_revalidated"])\n',
        '        self.assertTrue(report["taxonomy"]["source_revalidated"])\n',
        "source revalidation assertion",
    )
    text = replace_once(
        text,
        """            index_path = root / \"index.json\"
            report_path = root / \"report.json\"""",
        """            index_path = root / \"index.json\"
            taxonomy_source_path = root / \"selected_tags.csv\"
            report_path = root / \"report.json\"""",
        "CLI fixture paths",
    )
    text = replace_once(
        text,
        """            index_path.write_text(json.dumps(index), encoding=\"utf-8\")
            args = [""",
        """            index_path.write_text(json.dumps(index), encoding=\"utf-8\")
            taxonomy_source_path.write_bytes(taxonomy_source)
            args = [""",
        "CLI source fixture",
    )
    text = replace_once(
        text,
        """                \"--taxonomy-index\",
                str(index_path),
                \"--repo-root\",""",
        """                \"--taxonomy-index\",
                str(index_path),
                \"--taxonomy-source\",
                str(taxonomy_source_path),
                \"--repo-root\",""",
        "CLI source argument",
    )
    path.write_text(text, encoding="utf-8")


def patch_source_auth_tests() -> None:
    path = Path("tests/test_adult_illustration_prompt_membership_source_auth.py")
    text = path.read_text(encoding="utf-8")
    old = "projection, compiled, index = write_fixture(root)"
    count = text.count(old)
    if count != 3:
        raise SystemExit(
            f"source-auth fixture destructuring: expected three replacements, found {count}"
        )
    text = text.replace(
        old,
        "projection, compiled, index, _fixture_source = write_fixture(root)",
    )
    path.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    path = Path("docs/adult-illustration/TAXONOMY-MEMBERSHIP-INSPECTION.md")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "3. A taxonomy index built from the exact retained CSV and current review contracts:",
        "3. The exact retained taxonomy CSV.\n4. A taxonomy index built from those exact bytes and current review contracts:",
        "prerequisite list",
    )
    text = replace_once(
        text,
        """  --taxonomy-index .runtime/adult-illustration/taxonomy-index.json \\
  --out experiments/runs/hot-spring-membership.json""",
        """  --taxonomy-index .runtime/adult-illustration/taxonomy-index.json \\
  --taxonomy-source /reviewed/source/selected_tags.csv \\
  --out experiments/runs/hot-spring-membership.json""",
        "CLI example",
    )
    text = replace_once(
        text,
        "2. validates the saved index content identity and strict structure;",
        "2. deterministically rebuilds the index from the exact retained source bytes and current review contract;",
        "validation sequence",
    )
    text = replace_once(
        text,
        "The saved index's content identity is validated, but inspection does not receive source bytes. It therefore records:",
        "Inspection validates the exact retained source bytes before classifying source membership. It records:",
        "evidence identity prose",
    )
    text = replace_once(
        text,
        '  "source_revalidated": false',
        '  "source_revalidated": true',
        "evidence identity JSON",
    )
    text, count = re.subn(
        r"`source_revalidated: false` is not a failure\..*?required\.\n",
        "`source_revalidated: true` means the supplied source bytes reproduced the saved index exactly under the current finite review. A self-rehashed index is insufficient evidence.\n",
        text,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit(
            f"source revalidation explanation: expected one replacement, found {count}"
        )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_module()
    patch_cli()
    patch_tests()
    patch_source_auth_tests()
    patch_docs()


if __name__ == "__main__":
    main()
