"""Fixed Krita API operation: add a verified opaque edit as a new native layer.

Loaded by kritarunner from a hash-named, explicitly installed module. No network,
generation, shell commands, caller code, GUI document lookup or arbitrary output.
"""
import hashlib
import json
from pathlib import Path
import re

PROFILE = 'sRGB-elle-V2-srgbtrc.icc'
MAX_PIXELS = 16 * 1024 * 1024
INPUTS = {'native-source.kra', 'source.bgra', 'overlay.bgra', 'result.bgra'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def dependency_manifest(value):
    """Validate and order exact pins without reading paths or adopting aliases."""
    need(isinstance(value, list) and len(value) <= 256, 'Invalid native dependency manifest')
    result = []; seen = set()
    for item in value:
        need(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'Invalid native dependency identity')
        path, sha256 = item['path'], item['sha256']
        need(isinstance(path, str) and '\0' not in path and Path(path).is_absolute()
             and not path.startswith(('\\\\', '//')), 'Native dependencies require absolute local paths')
        need(isinstance(sha256, str) and re.fullmatch('[0-9a-f]{64}', sha256), 'Invalid native dependency hash')
        need(path not in seen, 'Duplicate native dependency path')
        seen.add(path); result.append({'path': path, 'sha256': sha256})
    return sorted(result, key=lambda item: item['path'])


def live_dependencies(plan):
    need('live_dependencies' in plan, 'Native package has no prepared dependency manifest; prepare a new package for live import')
    return dependency_manifest(plan['live_dependencies'])


def read_plan(path):
    path = Path(path).resolve(strict=True)
    plan = json.loads(path.read_text(encoding='utf-8'))
    need(plan.get('schema_version') == 1 and plan.get('operation') == 'character.krita-layer.v1', 'Unsupported native edit plan')
    need(plan.get('semantic_approval') is False and plan.get('neural_inference') is False, 'Invalid native edit claims')
    width, height = plan['canvas']
    need(type(width) is int and type(height) is int and width > 0 and height > 0 and width * height <= MAX_PIXELS, 'Unsupported native canvas')
    need(set(plan['files']) == INPUTS, 'Unexpected native input set')
    need(plan.get('profile') == PROFILE, 'Unsupported native profile')
    files = {}
    for name, record in plan['files'].items():
        source = path.parent / name
        need(not source.is_symlink() and source.resolve(strict=True).parent == path.parent, 'Native input escapes package')
        need(source.stat().st_size == record['bytes'], 'Native input size changed')
        need(source.stat().st_size <= 256 * 1024 * 1024, 'Native input exceeds byte budget')
        raw = source.read_bytes()
        need(digest(raw) == record['sha256'], 'Native input hash changed: ' + name)
        if name.endswith('.bgra'):
            need(len(raw) == width * height * 4, 'Native pixel buffer length is invalid')
        files[name] = raw
    need(all(a == 255 for a in files['source.bgra'][3::4]) and all(a == 255 for a in files['result.bgra'][3::4]), 'Native edit supports opaque source and result only')
    source, overlay, result = (files[n] for n in ('source.bgra', 'overlay.bgra', 'result.bgra'))
    for offset in range(0, len(source), 4):
        alpha = overlay[offset + 3]
        need(alpha in (0, 255), 'Native overlay must use binary coverage')
        expected = source[offset:offset + 4] if alpha == 0 else overlay[offset:offset + 4]
        need(expected == result[offset:offset + 4], 'Native overlay does not reproduce the verified result')
    return plan, files


def projection(document, width, height):
    document.waitForDone()
    document.refreshProjection()
    document.waitForDone()
    raw = bytes(document.pixelData(0, 0, width, height))
    need(len(raw) == width * height * 4, 'Krita returned an incomplete projection')
    return raw


def layers(document, width, height):
    nodes = document.topLevelNodes()
    need(1 <= len(nodes) <= 32, 'Native source supports 1..32 flat paint layers')
    result = []
    for node in nodes:
        need(node.type() == 'paintlayer' and not node.childNodes() and not node.animated(), 'Native source requires flat, non-animated paint layers')
        need(node.colorModel() == 'RGBA' and node.colorDepth() == 'U8' and node.colorProfile() == PROFILE, 'Unsupported layer color space')
        need(node.blendingMode() == 'normal', 'Native source requires normal paint layers')
        raw = bytes(node.pixelData(0, 0, width, height))
        need(len(raw) == width * height * 4, 'Incomplete native layer pixels')
        result.append({'name': node.name(), 'type': node.type(), 'visible': node.visible(),
                       'opacity': node.opacity(), 'locked': node.locked(), 'pixels_sha256': digest(raw)})
    return result


def execute(path, app):
    """Operate on an owned file copy, never an active user document."""
    path = Path(path).resolve(strict=True)
    root = path.parent
    plan, files = read_plan(path)
    for name in ('edited.kra', 'reopened.png', 'native-result.json', 'native-failure.json'):
        need(not (root / name).exists() and not (root / name).is_symlink(), 'Native output already exists; inspect the retained attempt')
    width, height = plan['canvas']
    document = None
    reopened = None
    try:
        document = app.openDocument(str(root / 'native-source.kra'))
        need(document is not None, 'Krita could not open the source copy')
        document.setBatchmode(True)
        need([document.width(), document.height()] == [width, height], 'Krita source canvas differs from edit plan')
        need(document.colorModel() == 'RGBA' and document.colorDepth() == 'U8' and document.colorProfile() == PROFILE, 'Krita source color space differs from supported profile')
        need(projection(document, width, height) == files['source.bgra'], 'Krita projection differs from the planned source; export a fresh document snapshot')
        original_layers = layers(document, width, height)
        need(len(original_layers) < 32, 'No capacity for another native layer')
        node = document.createNode('Proposed edit ' + plan['edit_plan_sha256'][:12], 'paintlayer')
        need(node is not None, 'Krita did not create a paint layer')
        need(document.rootNode().addChildNode(node, document.topLevelNodes()[-1]), 'Krita did not attach the edit layer')
        # Krita 5.2.16's Python binding returns None here despite the C++ bool
        # signature. Read the pixels back; return values do not prove a write.
        node.setPixelData(files['overlay.bgra'], 0, 0, width, height)
        document.waitForDone()
        need(bytes(node.pixelData(0, 0, width, height)) == files['overlay.bgra'], 'Krita did not write the exact edit pixels')
        need(projection(document, width, height) == files['result.bgra'], 'Native composition differs from verified pixels')
        need(layers(document, width, height)[:-1] == original_layers, 'Original native layers changed')
        node.setVisible(False)
        need(projection(document, width, height) == files['source.bgra'], 'Hiding the edit layer does not restore the original')
        node.setVisible(True)
        need(projection(document, width, height) == files['result.bgra'], 'Showing the edit layer does not restore the result')
        need(document.saveAs(str(root / 'edited.kra')), 'Krita could not save the new revision')
        document.setModified(False)
        document.close()
        document = None
        reopened = app.openDocument(str(root / 'edited.kra'))
        need(reopened is not None, 'Krita could not reopen the new revision')
        reopened.setBatchmode(True)
        need(projection(reopened, width, height) == files['result.bgra'], 'Reopened native projection changed')
        final_layers = layers(reopened, width, height)
        need(final_layers[:-1] == original_layers, 'Reopened original layers changed')
        from krita import InfoObject
        need(reopened.exportImage(str(root / 'reopened.png'), InfoObject()), 'Krita could not export the reopened revision')
        result = {'schema_version':1, 'operation':plan['operation'], 'edit_plan_sha256':plan['edit_plan_sha256'],
                  'native_plan_sha256':digest(path.read_bytes()), 'krita_version':app.version(),
                  'canvas':[width,height], 'profile':PROFILE, 'original_layers':original_layers, 'result_layers':final_layers,
                  'native_save_reopen_verified':True, 'native_projection_exact':True, 'hide_restores_source':True,
                  'neural_inference':False, 'semantic_approval':False, 'review_state':'unreviewed',
                  'outputs':{name:{'sha256':digest((root/name).read_bytes()), 'bytes':(root/name).stat().st_size} for name in ('edited.kra','reopened.png')}}
        (root / 'native-result.json').write_text(json.dumps(result,indent=2) + '\n',encoding='utf-8')
        return result
    except Exception as exc:
        (root / 'native-failure.json').write_text(json.dumps({'error':str(exc), 'edit_plan_sha256':plan['edit_plan_sha256']},indent=2) + '\n',encoding='utf-8')
        raise
    finally:
        for owned in (document, reopened):
            if owned is not None:
                owned.setModified(False)
                owned.close()


def run(args):
    need(len(args) == 1, 'One native-plan path required')
    from krita import Krita
    return execute(args[0], Krita.instance())
