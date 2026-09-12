"""Report installed distribution versions without importing inference packages."""
from __future__ import annotations

import importlib.metadata
import json
import re
import sys


def main(argv):
    if not 1 <= len(argv) <= 32:
        raise ValueError('Provide one to 32 distribution names')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name) for name in argv):
        raise ValueError('Invalid distribution name')
    observed = {}
    for name in argv:
        try:
            observed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            observed[name] = None
    sys.stdout.write(json.dumps(observed, sort_keys=True, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
