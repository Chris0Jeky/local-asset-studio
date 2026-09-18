"""Export the shared-workshop prototype as one offline HTML file (stdlib only)."""
import argparse
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/workshop'


def data_url(path: Path) -> str:
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path.suffix not in {'.png', '.svg'}:
        raise ValueError('Only repository PNG/SVG demo assets can be embedded')
    mime = 'image/png' if path.suffix == '.png' else 'image/svg+xml'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def stylesheet(path: Path, stack: tuple[Path, ...] = ()) -> str:
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path.suffix != '.css':
        raise ValueError('Styles must be repository CSS files')
    if path in stack:
        raise ValueError('Circular stylesheet import: ' + str(path))
    css = path.read_text(encoding='utf-8')
    def inline_import(match):
        imported = (path.parent / match.group(1)).resolve()
        return stylesheet(imported, stack + (path,))
    return re.sub(r"@import\s+url\(['\"]?([^'\")]+)['\"]?\)\s*;", inline_import, css)


def export() -> str:
    html = (SOURCE / 'prototype.html').read_text(encoding='utf-8')
    def style(match):
        attributes, relative = match.group(1), match.group(2)
        path = (SOURCE / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Styles must come from this repository')
        css = stylesheet(path)
        css = re.sub(r"url\(['\"]?/static/([^'\")]+)['\"]?\)", lambda m: "url('" + data_url(ROOT / 'app/static' / m.group(1)) + "')", css)
        css = re.sub(r"url\(['\"]?(workshop-assets/[^'\")]+)['\"]?\)", lambda m: "url('" + data_url(path.parent / m.group(1)) + "')", css)
        identity = ' id="workshopStyles"' if 'workshopStyles' in match.group(0) else ' id="workshopImmersiveStyles"' if 'workshopImmersiveStyles' in match.group(0) else ''
        return '<style' + identity + '>' + css + '</style>'
    html = re.sub(r'<link\s+([^>]*?)href="([^"]+)"[^>]*>', style, html)
    def script(match):
        path = (SOURCE / match.group(1)).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Scripts must come from this repository')
        return '<script>' + path.read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>'
    html = re.sub(r'<script src="([^"]+)"></script>', script, html)
    for relative in ['../../examples/workflow-lab/anima.png', '../../examples/gallery/pixel-lora-128.png']:
        html = html.replace(relative, data_url(SOURCE / relative))
    return html


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-prototype.html')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(export(), encoding='utf-8')
    print(args.output)
