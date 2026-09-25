"""Every relative Markdown link in a tracked document resolves to a present path.

Guards docs tidying and file moves: a moved page must take its inbound links with it. A target Git
deliberately ignores (local-only media such as `examples/local-only/`) may be absent. External URLs,
in-page anchors and links inside fenced or inline code are out of scope; anchors are not checked.
"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r'^ {0,3}(```|~~~).*?^ {0,3}\1', re.S | re.M)
INLINE_CODE = re.compile(r'`[^`\n]*`')
LINK = re.compile(r'\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
DEFINITION = re.compile(r'^ {0,3}\[[^\]\n]+\]:[ \t]*<?([^\s>]+)>?', re.M)
EXTERNAL = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|#|//)', re.I)
NUL = chr(0)


def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data, capture_output=True, check=data is None).stdout.decode('utf-8')


def tracked_markdown():
    return [ROOT / name for name in git('ls-files', '-z', '--', '*.md').split(NUL) if name]


def ignored(paths):
    if not paths: return set()
    return {name for name in git('check-ignore', '--no-index', '-z', '--stdin', data=NUL.join(paths).encode('utf-8')).split(NUL) if name}


def broken_links(path):
    text = INLINE_CODE.sub('', FENCE.sub('', path.read_text(encoding='utf-8', errors='replace')))
    for target in LINK.findall(text) + DEFINITION.findall(text):
        if EXTERNAL.match(target): continue
        target = unquote(target.split('#', 1)[0].split('?', 1)[0])
        if target and not (path.parent / target).exists(): yield target


class MarkdownLinkTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        try: files = tracked_markdown()
        except (OSError, subprocess.CalledProcessError): self.skipTest('git ls-files unavailable')
        self.assertGreater(len(files), 50)
        found = [(p, t, Path(os.path.relpath((p.parent / t).resolve(), ROOT)).as_posix()) for p in files for t in broken_links(p)]
        local_only = ignored(sorted({r for _, _, r in found}))
        broken = [f'{p.relative_to(ROOT).as_posix()} -> {t}' for p, t, r in found if r not in local_only]
        self.assertEqual(broken, [], 'broken relative Markdown links:\n' + '\n'.join(broken))

    def test_scanner_ignores_code_and_external_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            probe = Path(folder) / 'probe.md'
            probe.write_text('[a](https://x.test/y) [b](#top) `[c](nope.md)`\n```\n[d](nope.md)\n```\n  ```\n  [g](nope.md)\n  ```\n'
                             '[e](missing-page.md) [f](probe.md#x) [h][ref] [i][ok]\n\n[ref]: gone.md\n[ok]: probe.md "t"\n[web]: https://x.test\n', encoding='utf-8')
            self.assertEqual(list(broken_links(probe)), ['missing-page.md', 'gone.md'])

    def test_gitignored_local_only_targets_are_recognised(self):
        self.assertEqual(ignored(['examples/local-only/sheet.jpg', 'docs/README.md']), {'examples/local-only/sheet.jpg'})


if __name__ == '__main__':
    unittest.main()
