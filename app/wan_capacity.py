"""Admission guard for the retained Wan 2.2 untiled-decoder failure."""


LIMITS = {"max_side": 768, "max_pixels": 512 * 768, "max_frames": 33, "batch_size": 1}
SHAPE_KEYS = ("width", "height", "length", "batch_size")

def _ancestors(graph, link):
    pending = [link[0]] if isinstance(link, list) and len(link) == 2 else []
    seen = set()
    while pending:
        identifier = str(pending.pop())
        if identifier in seen: continue
        seen.add(identifier)
        node = graph.get(identifier, {})
        for value in node.get('inputs', {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], (str, int)) and type(value[1]) is int:
                pending.append(value[0])
    return seen


def projection(preset, graph):
    """Read-only catalogue data for the existing ordinary-decoder guard.

    Retain graph literals and exact control bindings, not a mode-name verdict.
    Dimensions may swap to match the source; the side/area envelope is symmetric.
    The UI batch count represents serial jobs, not a latent batch_size override.
    """
    identifiers = set()
    for decoder in graph.values():
        if decoder.get('class_type') == 'VAEDecode':
            identifiers.update(identifier for identifier in _ancestors(graph, decoder.get('inputs', {}).get('samples'))
                               if graph.get(identifier, {}).get('class_type') == 'Wan22ImageToVideoLatent')
    if not identifiers: return None
    latents = []
    for identifier in sorted(identifiers):
        bindings = []
        # Match prepare's application order. Companion-only controls remain visible.
        for key in ('frames', 'width', 'height'):
            targets = ([preset[key]] if preset.get(key) else []) + preset.get('bindings_extra', {}).get(key, [])
            for node, field in targets:
                if str(node) == identifier and field in SHAPE_KEYS:
                    bindings.append({'control': key, 'input': field})
        # Preserve Python's integer-only admission across JSON/JavaScript, where 1.0 == 1.
        inputs = graph[identifier].get('inputs', {})
        shape = {key: inputs.get(key) if type(inputs.get(key)) is int else None for key in SHAPE_KEYS}
        latents.append({'node': identifier, 'shape': shape, 'bindings': bindings})
    return {'version': 1, 'limits': dict(LIMITS), 'latents': latents}


def enforce(graph):
    """Check actual decoder inputs, including archived jobs without mode metadata.

    The historical 512x768/33-frame shape is an execution observation, not a
    promise of quality or success. Larger untiled workloads remain held until
    their decode plan has separate execution evidence. A tiled graph is a
    different experiment; this guard does not certify it.
    """
    for decoder in graph.values():
        if decoder.get('class_type') != 'VAEDecode': continue
        for identifier in _ancestors(graph, decoder.get('inputs', {}).get('samples')):
            node = graph.get(identifier, {})
            if node.get('class_type') != 'Wan22ImageToVideoLatent': continue
            inputs = node.get('inputs', {})
            shape = [inputs.get(key) for key in SHAPE_KEYS]
            if any(type(value) is not int or value < 1 for value in shape):
                raise ValueError('Wan VAE decode capacity cannot be checked: invalid latent dimensions')
            width, height, frames, batch = shape
            if max(width, height) <= LIMITS['max_side'] and width * height <= LIMITS['max_pixels'] and frames <= LIMITS['max_frames'] and batch == LIMITS['batch_size']:
                continue
            raise ValueError(
                f'Wan VAE decode capacity is unproven for {width}x{height}, {frames} frames, batch {batch}. '
                'The ordinary decoder is held beyond the recorded 512x768 / 33-frame envelope after the '
                '16 GiB GPU allocation failure. Choose Quick diagnostic or Balanced, or prove a separate '
                'tiled decode workflow before running this shape. No generation was submitted.'
            )
