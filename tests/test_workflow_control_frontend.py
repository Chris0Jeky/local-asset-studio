"""Page wiring contracts; native DOM and interaction live in the browser driver."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]

class Assets(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts=[]; self.styles=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='script' and 'src' in attrs: self.scripts.append(attrs['src'])
        if tag=='link' and attrs.get('rel')=='stylesheet': self.styles.append(attrs.get('href'))

class ControlFrontendTests(unittest.TestCase):
    def test_page_loads_the_preview_assets_once_after_the_editor_bridge(self):
        assets=Assets();assets.feed((ROOT/'app/static/workflow-studio.html').read_text(encoding='utf-8'))
        script='/static/workflow-control-preview.js';style='/static/workflow-control-preview.css'
        self.assertEqual(assets.scripts.count(script),1);self.assertEqual(assets.styles.count(style),1)
        self.assertGreater(assets.scripts.index(script),assets.scripts.index('/static/workflow-studio.js'))
        self.assertTrue((ROOT/'app'/script.lstrip('/')).is_file())
        self.assertTrue((ROOT/'app'/style.lstrip('/')).is_file())
    @unittest.skipUnless(shutil.which('node'),'Node required for shipped JavaScript syntax')
    def test_shipped_script_syntax(self):
        subprocess.run(['node','--check',str(ROOT/'app/static/workflow-control-preview.js')],check=True,
                       capture_output=True,text=True,timeout=15)
