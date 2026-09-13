"""Typed operations on one open Krita document; no network, queue or caller code.

Called synchronously on Krita's GUI thread. Never save/close the user's document.
Only capture clones are owned by this adapter. Hashes identify content, not people.
"""
import json
import os
from pathlib import Path
import struct
import uuid
import zlib

from . import native_edit as native


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def checked_path(value):
    path = Path(value)
    native.need(path.is_absolute() and not str(path).startswith(('\\\\', '//')), 'Use an absolute local artifact path')
    for parent in (path, *path.parents):
        if parent.exists():
            native.need(not parent.is_symlink() and not getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400,
                        'Native artifact paths cannot traverse links')
    return path.resolve()


def read_file(path, limit=256 * 1024**2):
    path = checked_path(path)
    native.need(path.is_file() and path.stat().st_size <= limit, 'Native artifact missing or exceeds byte budget')
    with path.open('rb') as stream: raw = stream.read(limit + 1)
    native.need(len(raw) <= limit, 'Native artifact exceeds byte budget')
    return raw


def read_json(path):
    return json.loads(read_file(path, 2 * 1024**2))


def publish(path, raw):
    path = checked_path(path)
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def record(path):
    return {'path': str(checked_path(path)), 'sha256': native.digest(read_file(path))}


def verified(record):
    native.need(isinstance(record, dict) and set(record) == {'path', 'sha256'}, 'Invalid native artifact identity')
    raw = read_file(record['path'])
    native.need(native.digest(raw) == record['sha256'], 'Native artifact hash changed')
    return raw


def rect(value):
    return [value.x(), value.y(), value.width(), value.height()]


def png_bytes(raw, width, height, gray=False):
    """Profile-free lossless snapshot, independent of export-dialog defaults."""
    channels = 1 if gray else 4
    native.need(len(raw) == width * height * channels, 'Incomplete snapshot pixel buffer')
    if not gray:
        rgba = bytearray(raw); rgba[0::4], rgba[2::4] = raw[2::4], raw[0::4]; raw = rgba
    stride = width * channels
    scan = b''.join(b'\0' + raw[y*stride:(y+1)*stride] for y in range(height))
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0 if gray else 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scan)) + chunk(b'IEND', b'')


def prepare_request(snapshot, native_plan, output, dependencies=()):
    """Bind a validated package to a capture. Production/canon checks stay upstream."""
    snapshot, native_plan = checked_path(snapshot), checked_path(native_plan)
    capture = read_json(snapshot); plan, buffers = native.read_plan(native_plan)
    native.need(capture['schema_version'] == 1 and capture['kind'] == 'krita_document_snapshot', 'Unsupported capture')
    native.need(native.digest(buffers['native-source.kra']) == capture['files']['source.kra']['sha256'], 'Native package has another captured source KRA')
    native.need(native.digest(buffers['source.bgra']) == capture['document']['projection_sha256'], 'Native package has another source projection')
    value = {'schema_version': 1, 'operation': 'character.krita-live-import.v1',
             'snapshot': record(snapshot), 'native_plan': record(native_plan),
             'dependencies': list(dependencies)}
    for item in value['dependencies']: verified(item)
    publish(output, canonical(value) + b'\n')
    return value


class Session:
    def __init__(self, document):
        native.need(document is not None, 'Select an open Krita document')
        self.document = document
        self.identifier = uuid.uuid4().hex
        self._captured = None
        self._applied = None

    def _snapshot(self):
        doc = self.document
        native.need(doc.tryBarrierLock(), 'Krita document is busy; finish the current operation and inspect again')
        try:
            width, height = doc.width(), doc.height()
            native.need(width > 0 and height > 0 and width * height <= native.MAX_PIXELS, 'Unsupported native canvas')
            native.need(doc.colorModel() == 'RGBA' and doc.colorDepth() == 'U8' and doc.colorProfile() == native.PROFILE, 'Unsupported native color space')
            nodes = doc.topLevelNodes()
            native.need(1 <= len(nodes) <= 32, 'Native session requires 1..32 flat paint layers')
            layers = []; extent_pixels = 0
            for node in nodes:
                native.need(node.type() == 'paintlayer' and not node.childNodes() and not node.animated(), 'Native session requires flat non-animated paint layers')
                native.need(node.colorModel() == 'RGBA' and node.colorDepth() == 'U8' and node.colorProfile() == native.PROFILE and node.blendingMode() == 'normal', 'Unsupported native layer color or blending')
                bounds = rect(node.bounds()); x,y,w,h = bounds
                extent_pixels += w*h
                native.need(w >= 0 and h >= 0 and w*h <= native.MAX_PIXELS and extent_pixels <= native.MAX_PIXELS*4, 'Native layer extents exceed inspection budget')
                raw = bytes(node.pixelData(x,y,w,h)) if w and h else b''
                native.need(len(raw) == w*h*4, 'Incomplete native layer pixels')
                style = node.layerStyleToAsl()
                layers.append({'id': str(node.uniqueId()), 'name': node.name(), 'bounds': bounds,
                               'visible': node.visible(), 'opacity': node.opacity(), 'locked': node.locked(),
                               'alpha_locked': node.alphaLocked(), 'inherit_alpha': node.inheritAlpha(),
                               'style_sha256': native.digest(style.encode('utf-8')), 'pixels_sha256': native.digest(raw)})
            raw = bytes(doc.pixelData(0,0,width,height))
            native.need(len(raw) == width*height*4, 'Incomplete native projection')
            selection = doc.selection(); selected = None; selection_record = None
            if selection is not None:
                bounds = [selection.x(),selection.y(),selection.width(),selection.height()]
                x,y,w,h = bounds
                native.need(w >= 0 and h >= 0 and w*h <= native.MAX_PIXELS, 'Native selection exceeds inspection budget')
                extent = bytes(selection.pixelData(x,y,w,h)) if w and h else b''
                selected = bytes(selection.pixelData(0,0,width,height))
                native.need(len(extent) == w*h and len(selected) == width*height, 'Incomplete selection pixels')
                selection_record = {'bounds': bounds, 'sha256': native.digest(extent), 'canvas_sha256': native.digest(selected)}
            document = {'root_id': str(doc.rootNode().uniqueId()), 'canvas': [width,height],
                        'profile': native.PROFILE, 'filename': doc.fileName(), 'modified': doc.modified(),
                        'layers': layers, 'selection': selection_record, 'projection_sha256': native.digest(raw)}
            snapshot = {'schema_version': 1, 'kind': 'krita_document_snapshot', 'session_id': self.identifier,
                        'document': document, 'revision_sha256': native.digest(canonical(document))}
            return snapshot, raw, selected
        finally:
            doc.unlock()

    def inspect(self):
        return self._snapshot()[0]

    def capture(self, output):
        folder = checked_path(output)
        folder.mkdir()  # Existing and partial captures are never overwritten.
        snapshot, raw, selected = self._snapshot()
        native.need(all(a == 255 for a in raw[3::4]), 'Native capture currently requires an opaque projection')
        width, height = snapshot['document']['canvas']
        clone = None
        try:
            publish(folder/'source.bgra', raw)
            publish(folder/'source.png', png_bytes(raw,width,height))
            if selected is not None:
                publish(folder/'selection.gray', selected)
                publish(folder/'selection.png', png_bytes(selected,width,height,True))
            clone = self.document.clone()
            native.need(clone is not None and clone is not self.document, 'Krita could not clone the source')
            clone.setBatchmode(True)
            native.need(clone.saveAs(str(folder/'source.kra')), 'Krita could not save the capture clone')
            native.need(self.inspect() == snapshot, 'Native document became stale during capture; retain this partial capture')
            names = ['source.kra', 'source.bgra', 'source.png'] + (['selection.gray','selection.png'] if selected is not None else [])
            snapshot['files'] = {name: {'sha256': native.digest(read_file(folder/name))} for name in names}
            publish(folder/'snapshot.json', canonical(snapshot) + b'\n')
            self._captured = record(folder/'snapshot.json')
            return snapshot
        finally:
            if clone is not None and clone is not self.document:
                clone.setModified(False); clone.close()

    def _settle(self):
        self.document.waitForDone(); self.document.refreshProjection(); self.document.waitForDone()

    def import_request(self, path):
        request = read_json(path)
        native.need(set(request) == {'schema_version','operation','snapshot','native_plan','dependencies'}
                    and request['schema_version'] == 1 and request['operation'] == 'character.krita-live-import.v1', 'Unsupported native command')
        snapshot = json.loads(verified(request['snapshot']))
        native.need(snapshot['session_id'] == self.identifier and request['snapshot'] == self._captured, 'Native capture belongs to another session')
        native.need(self._applied is None, 'This session already imported a proposed layer; inspect it before another capture')
        native_path = checked_path(request['native_plan']['path']); root = native_path.parent
        native.need(not any((root/name).exists() for name in ('live-intent.json','live-result.json','live-failure.json')), 'Native attempt already retained; do not repeat the import')
        verified(request['native_plan'])
        native.need(isinstance(request['dependencies'],list) and len(request['dependencies']) <= 256, 'Invalid native dependency list')
        for item in request['dependencies']: verified(item)
        plan, buffers = native.read_plan(native_path)
        native.need(native.digest(buffers['native-source.kra']) == snapshot['files']['source.kra']['sha256'], 'Native source KRA differs from capture')
        current, raw, _ = self._snapshot()
        native.need(current['revision_sha256'] == snapshot['revision_sha256'], 'Native document is stale; capture its current unsaved revision')
        native.need(raw == buffers['source.bgra'] and current['document']['canvas'] == plan['canvas'], 'Native source projection differs from prepared result')
        native.need(len(current['document']['layers']) < 32, 'No capacity for another native layer')
        publish(root/'live-intent.json', canonical({'request':record(path),'session_id':self.identifier,'revision_sha256':current['revision_sha256']}) + b'\n')
        node = None
        try:
            # Krita callbacks run on the GUI thread. Recheck after filesystem IO;
            # no event loop is entered between this guard and attaching the layer.
            native.need(self.inspect() == current, 'Native document became stale before import')
            node = self.document.createNode('Proposed edit ' + plan['edit_plan_sha256'][:12], 'paintlayer')
            native.need(node is not None, 'Krita did not create a proposed layer')
            native.need(self.document.rootNode().addChildNode(node,self.document.topLevelNodes()[-1]), 'Krita did not attach proposed layer')
            self.document.setModified(True)
            width,height = plan['canvas']
            node.setPixelData(buffers['overlay.bgra'],0,0,width,height)
            self._settle()
            native.need(bytes(node.pixelData(0,0,width,height)) == buffers['overlay.bgra'], 'Krita did not write the exact proposed pixels')
            after = self.inspect()
            native.need(after['document']['layers'][:-1] == current['document']['layers'], 'Original native layers changed during import')
            native.need(after['document']['selection'] == current['document']['selection'], 'Native selection changed during import')
            native.need(after['document']['projection_sha256'] == native.digest(buffers['result.bgra']), 'Native proposed projection differs from result')
            node.setVisible(False); self._settle()
            native.need(self.inspect()['document']['projection_sha256'] == current['document']['projection_sha256'], 'Hiding proposed layer did not restore source')
            node.setVisible(True); self._settle()
            after = self.inspect()
            native.need(after['document']['projection_sha256'] == native.digest(buffers['result.bgra']), 'Showing proposed layer did not restore result')
            self._applied = {'node':node, 'revision':after['revision_sha256'], 'source':current['document']['projection_sha256'],
                             'result':native.digest(buffers['result.bgra']), 'directory':root, 'sequence':0}
            receipt = {'schema_version':1, 'operation':request['operation'], 'session_id':self.identifier,
                       'native_plan_sha256':request['native_plan']['sha256'], 'before':current, 'after':after,
                       'layer_id':str(node.uniqueId()), 'source_restoration_verified':True,
                       'neural_inference':False, 'semantic_approval':False, 'review_state':'unreviewed'}
            publish(root/'live-result.json', canonical(receipt) + b'\n')
            return receipt
        except Exception as exc:
            publish(root/'live-failure.json', canonical({'error':str(exc),'layer_id':str(node.uniqueId()) if node is not None else None,
                                                       'work_preserved':True,'automatic_retry':False}) + b'\n')
            raise

    def _show(self, result):
        native.need(self._applied is not None, 'This session has no imported layer')
        applied = self._applied
        current = self.inspect()
        native.need(current['revision_sha256'] == applied['revision'], 'Native document is stale; preserve user edits and inspect the layers manually')
        number = applied['sequence'] + 1
        path = applied['directory']/('compare-%04d-intent.json' % number)
        publish(path, canonical({'revision_sha256':current['revision_sha256'],'show_result':result}) + b'\n')
        # Invalidate before mutation; a failed comparison never grants replay.
        applied['revision'] = None; applied['sequence'] = number
        applied['node'].setVisible(result); self._settle()
        after = self.inspect()
        native.need(after['document']['projection_sha256'] == applied['result' if result else 'source'], 'Native comparison projection changed unexpectedly')
        publish(path.with_name('compare-%04d-result.json' % number), canonical(after) + b'\n')
        applied['revision'] = after['revision_sha256']
        return after

    def show_source(self):
        return self._show(False)

    def show_result(self):
        return self._show(True)
