#!/usr/bin/env python3
"""Execute the retained #486 patch body after repairing one nested string literal."""
from __future__ import annotations

from pathlib import Path
import textwrap


WORKFLOW = Path(".github/workflows/issue-486-patch.yml")
START = "          python - <<'PY'\n"
END = "\n          PY\n"


def main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index(START) + len(START)
    end = workflow.index(END, start)
    source = textwrap.dedent(workflow[start:end])

    broken = '''                      script = """nodes => nodes.filter(node => {
                        const style = getComputedStyle(node), rect = node.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                      }).map(node => node.getAttribute(%s))""" % json.dumps(attribute)'''
    repaired = '''                      script = (
                        "nodes => nodes.filter(node => {"
                        "const style = getComputedStyle(node), rect = node.getBoundingClientRect();"
                        "return rect.width > 0 && rect.height > 0 && "
                        "style.display !== 'none' && style.visibility !== 'hidden';"
                        "}).map(node => node.getAttribute(%s))"
                      ) % json.dumps(attribute)'''
    if source.count(broken) != 1:
        raise SystemExit(
            "Expected exactly one nested JavaScript string in retained #486 patch body"
        )
    source = source.replace(broken, repaired)
    compile(source, str(WORKFLOW) + "::<issue-486-patch>", "exec")
    namespace = {"__name__": "__main__", "__file__": str(WORKFLOW)}
    exec(source, namespace, namespace)


if __name__ == "__main__":
    main()
