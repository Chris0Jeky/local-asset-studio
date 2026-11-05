"""Run inside the selected Blender before the production shading qualification."""
import hashlib
import json
from pathlib import Path
import platform
import sys

import bpy


def main():
    descriptor, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
    selection = json.loads(descriptor.read_text(encoding='utf-8'))
    decode = lambda value: value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
    receipt = {'state': 'failed', 'version': list(bpy.app.version), 'version_string': bpy.app.version_string,
               'build_hash': decode(bpy.app.build_hash), 'build_date': decode(bpy.app.build_date),
               'build_time': decode(bpy.app.build_time), 'build_platform': decode(bpy.app.build_platform),
               'binary_path': bpy.app.binary_path, 'python': sys.version, 'python_executable': sys.executable,
               'sys_path': sys.path, 'platform': platform.platform(), 'machine': platform.machine(),
               'expected_version': selection['version'], 'expected_build_hash': selection['build_hash']}
    try:
        if list(bpy.app.version)[:2] != [5, 4] or receipt['build_hash'] != selection['build_hash']:
            raise RuntimeError('Selected Blender 5.4 build identity does not match runtime')
        import numpy
        import io_scene_gltf2
        receipt['numpy'] = {'version': numpy.__version__, 'path': numpy.__file__}
        module = Path(io_scene_gltf2.__file__)
        sources = sorted(module.parent.rglob('*.py'))
        hashes = {str(path.relative_to(module.parent)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        receipt['gltf_exporter'] = {'path': str(module), 'bl_info': getattr(io_scene_gltf2, 'bl_info', None),
                                    'source_sha256': hashes}
        properties = bpy.ops.export_scene.gltf.get_rna_type().properties
        receipt['export_normals_default'] = properties['export_normals'].default
        if not receipt['export_normals_default']: raise RuntimeError('Production exporter default omits normals')
        receipt['state'] = 'passed'
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
