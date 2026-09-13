"""Causal open-document checks; these fakes are not native execution evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from integrations.krita import native_edit
from integrations.krita import document_session as ds


class Rect:
    def __init__(self, x=0, y=0, w=2, h=2): self.values = (x, y, w, h)
    def x(self): return self.values[0]
    def y(self): return self.values[1]
    def width(self): return self.values[2]
    def height(self): return self.values[3]


class Node:
    def __init__(self, name, raw, visible=True):
        self.label, self.raw, self.shown = name, raw, visible
        self.id = uuid.uuid4().hex; self.rect = Rect(); self.failed_write = False
    def uniqueId(self): return self.id
    def name(self): return self.label
    def type(self): return 'paintlayer'
    def childNodes(self): return []
    def animated(self): return False
    def colorModel(self): return 'RGBA'
    def colorDepth(self): return 'U8'
    def colorProfile(self): return native_edit.PROFILE
    def blendingMode(self): return 'normal'
    def visible(self): return self.shown
    def setVisible(self, value): self.shown = value
    def opacity(self): return 255
    def locked(self): return False
    def alphaLocked(self): return False
    def inheritAlpha(self): return False
    def layerStyleToAsl(self): return ''
    def bounds(self): return self.rect
    def pixelData(self, *args): return self.raw
    def setPixelData(self, raw, *args):
        if not self.failed_write: self.raw = bytes(raw)


class Root:
    def __init__(self, doc): self.doc = doc; self.id = uuid.uuid4().hex
    def uniqueId(self): return self.id
    def addChildNode(self, node, sibling): self.doc.nodes.append(node); return True


class Selection:
    def __init__(self): self.raw = bytes([255, 0, 0, 0])
    def pixelData(self, *args): return self.raw
    def x(self): return 0
    def y(self): return 0
    def width(self): return 2
    def height(self): return 2


class SelectionNode(Node):
    def type(self): return 'selectionmask'


class Document:
    def __init__(self):
        self.source = bytes([30, 20, 10, 255]) * 4
        self.nodes = [Node('Hidden original', b'\x00' * 16, False), Node('Visible original', self.source)]
        self.root = Root(self); self.sel = Selection(); self.dirty = True
        self.closed = False; self.saved = []; self.failed_write = False; self.busy = False
    def width(self): return 2
    def height(self): return 2
    def colorModel(self): return 'RGBA'
    def colorDepth(self): return 'U8'
    def colorProfile(self): return native_edit.PROFILE
    def rootNode(self): return self.root
    def topLevelNodes(self): return self.nodes
    def selection(self): return self.sel
    def modified(self): return self.dirty
    def fileName(self): return ''
    def waitForDone(self): pass
    def refreshProjection(self): pass
    def tryBarrierLock(self): return not self.busy
    def unlock(self): pass
    def clone(self): return copy.deepcopy(self)
    def setBatchmode(self, value): pass
    def saveAs(self, path): self.saved.append(path); Path(path).write_bytes(b'fixture native copy'); return True
    def setModified(self, value): self.dirty = value
    def close(self): self.closed = True
    def pixelData(self, *args):
        output = bytearray(16)
        for node in self.nodes:
            if node.shown:
                for i in range(0, 16, 4):
                    if node.raw[i+3]: output[i:i+4] = node.raw[i:i+4]
        return bytes(output)
    def createNode(self, name, kind):
        node = Node(name, b'\x00' * 16); node.failed_write = self.failed_write; return node


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.doc = Document(); self.session = ds.Session(self.doc)
        self.capture = self.root/'capture'; self.session.capture(self.capture)
        self.package = self.root/'package'; self.package.mkdir()
        self.result = bytes([70, 80, 90, 255]) + self.doc.source[4:]
        buffers = {'native-source.kra': (self.capture/'source.kra').read_bytes(),
                   'source.bgra': self.doc.source, 'overlay.bgra': self.result[:4] + b'\x00' * 12,
                   'result.bgra': self.result}
        self.plan = {'schema_version': 1, 'operation': 'character.krita-layer.v1', 'live_dependencies': [],
                     'canvas': [2, 2], 'profile': native_edit.PROFILE, 'edit_plan_sha256': 'a'*64,
                     'semantic_approval': False, 'neural_inference': False, 'changed_pixels': 1,
                     'files': {n: {'bytes': len(b), 'sha256': native_edit.digest(b)} for n,b in buffers.items()}}
        for name, raw in buffers.items(): (self.package/name).write_bytes(raw)
        self.native = self.package/'native-plan.json'; self.native.write_text(json.dumps(self.plan))
        self.request = self.root/'import.json'
        ds.prepare_request(self.capture/'snapshot.json', self.native, self.request)

    def test_capture_keeps_unsaved_original_and_exports_exact_snapshot(self):
        self.assertTrue(self.doc.dirty); self.assertFalse(self.doc.closed); self.assertEqual(self.doc.saved, [])
        self.assertEqual((self.capture/'source.bgra').read_bytes(), self.doc.source)
        self.assertEqual((self.capture/'selection.gray').read_bytes(), self.doc.sel.raw)
        self.assertEqual(self.session.inspect()['revision_sha256'], json.loads((self.capture/'snapshot.json').read_text())['revision_sha256'])

    def test_import_and_comparison_preserve_originals_and_unsaved_document(self):
        original = copy.deepcopy(self.session.inspect()['document']['layers'])
        receipt = self.session.import_request(self.request)
        self.assertFalse(receipt['semantic_approval']); self.assertFalse(receipt['neural_inference'])
        self.assertEqual(self.doc.pixelData(), self.result)
        self.assertEqual(self.session.inspect()['document']['layers'][:-1], original)
        self.session.show_source(); self.assertEqual(self.doc.pixelData(), self.doc.source)
        self.session.show_result(); self.assertEqual(self.doc.pixelData(), self.result)
        self.assertEqual(len(self.doc.nodes), 3); self.assertTrue(self.doc.dirty)
        self.assertEqual(self.doc.saved, []); self.assertFalse(self.doc.closed)

    def test_each_stale_native_revision_rejects_before_intent_or_layer(self):
        for change in ('hidden_pixels', 'selection', 'order', 'name', 'outside_extent', 'dirty_flag'):
            with self.subTest(change=change):
                doc = copy.deepcopy(self.doc); self.session.document = doc
                if change == 'hidden_pixels': doc.nodes[0].raw = b'\x01' * 16
                elif change == 'selection': doc.sel.raw = bytes([0, 255, 0, 0])
                elif change == 'order': doc.nodes.reverse()
                elif change == 'name': doc.nodes[0].label = 'Human rename'
                elif change == 'outside_extent': doc.nodes[0].rect = Rect(-1, 0, 2, 2)
                elif change == 'dirty_flag': doc.dirty = False
                with self.assertRaisesRegex(ValueError, 'stale'): self.session.import_request(self.request)
                self.assertEqual(len(doc.nodes), 2)
                self.assertFalse((self.package/'live-intent.json').exists())

    def test_changed_candidate_or_source_package_rejects_before_layer(self):
        (self.package/'overlay.bgra').write_bytes(b'\x00' * 16)
        with self.assertRaisesRegex(ValueError, 'hash changed'): self.session.import_request(self.request)
        self.assertEqual(len(self.doc.nodes), 2)

    def test_failed_write_retains_attempt_and_never_reimports(self):
        self.doc.failed_write = True
        with self.assertRaisesRegex(ValueError, 'write'): self.session.import_request(self.request)
        self.assertTrue((self.package/'live-intent.json').exists())
        self.assertTrue((self.package/'live-failure.json').exists())
        self.assertEqual(len(self.doc.nodes), 3)
        with self.assertRaises(ValueError): self.session.import_request(self.request)
        self.assertEqual(len(self.doc.nodes), 3)
        self.assertEqual(self.doc.nodes[1].raw, self.doc.source)

    def test_repeat_import_cannot_add_another_layer(self):
        self.session.import_request(self.request)
        with self.assertRaises(ValueError): self.session.import_request(self.request)
        self.assertEqual(len(self.doc.nodes), 3)

    def test_import_marks_previously_clean_document_modified(self):
        self.doc.dirty = False
        self.session.capture(self.root/'clean-capture')
        ds.prepare_request(self.root/'clean-capture/snapshot.json', self.native, self.root/'clean-import.json')
        self.session.import_request(self.root/'clean-import.json')
        self.assertTrue(self.doc.modified())

    def test_human_edit_to_proposed_or_hidden_layer_blocks_compare(self):
        self.session.import_request(self.request)
        for index in (0, 2):
            with self.subTest(index=index):
                before = self.doc.nodes[index].raw
                self.doc.nodes[index].raw = b'\x02' * 16
                with self.assertRaisesRegex(ValueError, 'stale'): self.session.show_source()
                self.assertTrue(self.doc.nodes[2].visible())
                self.doc.nodes[index].raw = before

    def test_other_session_cannot_apply_captured_request(self):
        with self.assertRaisesRegex(ValueError, 'session'): ds.Session(self.doc).import_request(self.request)
        self.assertEqual(len(self.doc.nodes), 2)

    def test_busy_document_is_not_read_or_changed(self):
        self.doc.busy = True
        with self.assertRaisesRegex(ValueError, 'busy'): self.session.import_request(self.request)
        self.assertFalse((self.package/'live-intent.json').exists())

    def test_native_global_selection_node_is_bound_separately_from_paint_layers(self):
        self.doc.nodes.append(SelectionNode('Selection Mask', self.doc.sel.raw, False))
        snapshot = self.session.capture(self.root/'selected-capture')
        self.assertEqual(len(snapshot['document']['layers']), 2)
        self.assertEqual(snapshot['document']['selection_node']['pixels_sha256'], native_edit.digest(self.doc.sel.raw))
        self.doc.nodes[-1].raw = bytes([0,255,0,0])
        with self.assertRaisesRegex(ValueError, 'selection'): self.session.inspect()

    def test_capture_and_request_refuse_overwrite(self):
        with self.assertRaises(FileExistsError): self.session.capture(self.capture)
        with self.assertRaises(FileExistsError): ds.prepare_request(self.capture/'snapshot.json', self.native, self.request)


if __name__ == '__main__': unittest.main()
