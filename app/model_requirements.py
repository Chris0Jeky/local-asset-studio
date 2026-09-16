"""Read-only preset dependency projection over the existing curated model library.

A loader contract or explicit declaration supplies a folder, never a basename match.
Presence, install eligibility and runtime compatibility are independent observations.
"""
from pathlib import Path
import stat

from download_contracts import relative_model_path, validate_pins
from model_library import FOLDERS, SUFFIXES

from studio_workflow.model_contracts import ANNOTATOR_SELECTIONS, MODEL_INPUT_FOLDERS

# Do not misclassify ordinary prompt/output text merely because it ends in a suffix.
TEXT_FIELDS = {'text', 'prompt', 'positive', 'negative', 'filename_prefix'}


def model_selection(kind, field, value):
    if (kind, field) in ANNOTATOR_SELECTIONS: return False
    return isinstance(value, str) and ((kind, field) in MODEL_INPUT_FOLDERS or
        field not in TEXT_FIELDS and Path(value).suffix.lower() in SUFFIXES | {'.patch'})


def declared_path(value):
    path = relative_model_path(value)
    if len(path.parts) < 2 or path.parts[0] not in FOLDERS:
        raise ValueError('Declare a relative file in a supported model folder')
    return path.as_posix()


def _presence(root, relative, observations):
    key = (str(root), relative)
    if key not in observations:
        target = root / relative
        try:
            # Check lexical children before resolving, including broken symlinks.
            for item in (target, *target.parents):
                if item == root: break
                if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
                    raise ValueError('Model path is a link; inspect the declared location')
            path = target.resolve()
            if not path.is_relative_to(root): raise ValueError('Model path escapes its backend library')
            try: info = path.stat()
            except FileNotFoundError: info = None
            present = info is not None and stat.S_ISREG(info.st_mode) and info.st_size > 0
            occupied = info is not None
            note = ('File present; content and runtime compatibility are separate checks.' if present else
                    'Destination is occupied by an empty or non-regular entry; inspect it before choosing a replacement.' if occupied else
                    'Missing file; place it in the indicated folder.')
            observations[key] = (str(path), present, note, occupied)
        except (OSError, ValueError) as exc:
            observations[key] = (None, None, 'File availability unknown: ' + str(exc)[:250], None)
    return observations[key]


def requirements(library, preset, graph, model_root, *, assets=None, observations=None):
    """Project exact paths, cheap presence and existing installer policy. Never write."""
    root = Path(model_root).resolve()
    observations = {} if observations is None else observations
    assets = library.manifest().get('assets', []) if assets is None else assets
    known = {}
    for asset in assets:
        if isinstance(asset, dict) and isinstance(asset.get('file'), str):
            known.setdefault(asset['file'], []).append(asset)
    declarations = preset.get('model_files', [])
    if not isinstance(declarations, list): raise ValueError('model_files must be a list of relative model paths')
    declarations = list(dict.fromkeys(declared_path(value) for value in declarations))
    rows = {}

    def add(relative, binding=None, selection=None, error=None):
        key = relative if relative is not None else ('unknown', binding, selection)
        if key in rows: return
        row = {'file': relative or selection, 'folder': relative.split('/')[0] if relative else None,
               'path': None, 'present': None, 'occupied': None, 'asset_id': None, 'source': None,
               'installable': False, 'install_note': error, 'note': error}
        if relative is not None:
            row['path'], row['present'], row['note'], row['occupied'] = _presence(root, relative, observations)
            pins = known.get(relative, [])
            if len(pins) == 1:
                asset = pins[0]; row.update(asset_id=asset.get('id'), source=asset.get('source'))
                try:
                    validate_pins(asset)
                    if row['present'] is None or row['occupied'] is True and row['present'] is False: blocked = row['note']
                    elif root != library.models.resolve(): blocked = 'Select the matching backend explicitly before using its model installer.'
                    else: blocked = library.install_block(asset, row['present'])
                except (ValueError, OSError) as exc: blocked = str(exc)
                row.update(installable=blocked is None, install_note=blocked)
            else:
                row['install_note'] = ('Multiple exact-path pins need review; automatic installation is unavailable.' if pins else
                    'No exact-path curated pin; review the source and checksum before installing manually.')
        rows[key] = row

    for relative in declarations: add(relative)
    for node_id, node in graph.items():
        kind = node.get('class_type')
        for field, value in node.get('inputs', {}).items():
            if not model_selection(kind, field, value): continue
            # Comfy selections may use native Windows separators; manifest paths stay portable.
            selection = value.replace('\\', '/')
            try:
                relative_model_path(selection)
                folder = MODEL_INPUT_FOLDERS.get((kind, field))
                if folder: relative = declared_path(folder + '/' + selection)
                else:
                    matches = [path for path in declarations if path == selection or path.endswith('/' + selection)]
                    if len(matches) != 1: raise ValueError('Model folder unknown or ambiguous; declare its exact relative path in model_files.')
                    relative = matches[0]
                add(relative)
            except ValueError as exc:
                add(None, (str(node_id), field), value, f'{kind}.{field}: {exc}')
    return list(rows.values())
