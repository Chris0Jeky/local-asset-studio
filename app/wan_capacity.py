"""Admission guard for the retained Wan 2.2 untiled-decoder failure."""


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
            shape = [inputs.get(key) for key in ('width', 'height', 'length', 'batch_size')]
            if any(type(value) is not int or value < 1 for value in shape):
                raise ValueError('Wan VAE decode capacity cannot be checked: invalid latent dimensions')
            width, height, frames, batch = shape
            if max(width, height) <= 768 and width * height <= 512 * 768 and frames <= 33 and batch == 1:
                continue
            raise ValueError(
                f'Wan VAE decode capacity is unproven for {width}x{height}, {frames} frames, batch {batch}. '
                'The ordinary decoder is held beyond the recorded 512x768 / 33-frame envelope after the '
                '16 GiB GPU allocation failure. Choose Quick diagnostic or Balanced, or prove a separate '
                'tiled decode workflow before running this shape. No generation was submitted.'
            )
