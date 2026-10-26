"""Regular-only schema projections without mutating ComfyUI's execution cache.

Runtime file-choice lists can include staged private references. Those choices
also enter raw descriptor evidence and schema hashes, so remove them before any
public catalog/control projection is constructed. Workflow authoring remains a
regular-only surface; private image execution still uses the unmodified cache.
"""
import copy
from contextlib import nullcontext
from pathlib import Path
import re


def public_node_info(studio, refresh=False):
    info=studio.node_info(True) if refresh else studio.node_info()
    names=set()
    experiments=getattr(studio,'experiments',None)
    if experiments is not None:
        private=Path(experiments)/'private';uploads=private/'uploads'
        try:
            if private.is_symlink() or uploads.is_symlink():
                raise ValueError('Public node choices are unavailable while private source storage needs inspection')
            if uploads.exists():
                for entry in uploads.iterdir():
                    names.add(entry.name.removesuffix('.json'))
        except OSError:
            raise ValueError('Public node choices are unavailable while private source storage needs inspection') from None
    # A retained private source is still private if its Studio staging copy was
    # lost. ComfyUI may retain the input; do not redisclose that name on reload.
    with getattr(studio,'lock',nullcontext()):
        for job in getattr(studio,'jobs',{}).values():
            if not isinstance(job,dict) or job.get('privacy','regular')=='regular':continue
            controls=job.get('controls',{})
            if isinstance(controls,dict):
                names.update(value for key,value in controls.items() if key in ('reference','last_reference') and isinstance(value,str) and value)
            for reference in job.get('references',[]) if isinstance(job.get('references',[]),list) else []:
                if isinstance(reference,dict) and isinstance(reference.get('file'),str) and reference['file']:names.add(reference['file'])
    pattern=re.compile('|'.join(re.escape(name) for name in sorted(names))) if names else None
    omitted=object()

    def hidden(value):
        return isinstance(value,str) and (bool(pattern and pattern.search(value)) or 'local-asset-studio/private/' in value.replace('\\','/').lower())

    def project(value):
        if hidden(value):return omitted
        if isinstance(value,list):return [item for child in value if (item:=project(child)) is not omitted]
        if isinstance(value,dict):return {key:item for key,child in value.items() if not hidden(key) and (item:=project(child)) is not omitted}
        return copy.deepcopy(value)

    return project(info)
