"""Opt-in loader experiment for H3's Windows safetensors access violation.

No site-package edits. Only explicitly selected local H3 model files are intercepted.
The normal loader remains in use for every other file and every GPU load.
"""
import json
import math
import mmap
import os
from pathlib import Path
import struct
import warnings


def _unique_object(pairs):
    value={}
    for key,item in pairs:
        # ascii() keeps an unpaired-surrogate key encodable wherever the refusal is logged or projected (#736).
        if key in value:raise ValueError('duplicate safetensors header key: '+ascii(key[:120]))
        value[key]=item
    return value


def _reject_constant(value):
    raise ValueError('non-finite JSON constant in safetensors header: '+value)


def checked_header(stream, size, dtypes):
    prefix=stream.read(8)
    if len(prefix)!=8:raise ValueError('Incomplete safetensors prefix')
    length=struct.unpack('<Q',prefix)[0]
    if not 2<=length<=16*1024**2 or 8+length>size:raise ValueError('Invalid safetensors header length')
    raw=stream.read(length)
    if len(raw)!=length:raise ValueError('Incomplete safetensors header')
    header=json.loads(raw,object_pairs_hook=_unique_object,parse_constant=_reject_constant);base=8+length;spans=[]
    if not isinstance(header,dict):raise ValueError('Invalid safetensors header')
    for name,entry in header.items():
        if name=='__metadata__':continue
        if not isinstance(entry,dict) or entry.get('dtype') not in dtypes:raise ValueError('Unknown tensor dtype')
        shape=entry.get('shape');offsets=entry.get('data_offsets')
        if not isinstance(shape,list) or any(type(n) is not int or n<0 for n in shape):raise ValueError('Invalid tensor shape')
        if not isinstance(offsets,list) or len(offsets)!=2 or any(type(n) is not int for n in offsets):raise ValueError('Invalid tensor offsets')
        lo,hi=offsets
        if lo<0 or hi<lo or hi>size-base or hi-lo!=math.prod(shape)*dtypes[entry['dtype']].itemsize:raise ValueError('Tensor extent does not match its shape and file')
        spans.append((lo,hi))
    cursor=0
    for lo,hi in sorted(spans):
        if lo!=cursor:raise ValueError('Overlapping or missing tensor data')
        cursor=hi
    if cursor!=size-base:raise ValueError('Unclaimed safetensors payload')
    return header,base


def load_cpu(path, torch, dtypes, read_only=False):
    path=Path(path).resolve()
    with path.open('rb') as stream:
        header,base=checked_header(stream,os.fstat(stream.fileno()).st_size,dtypes)
        # Copy-on-write protects the original file while giving Torch writable storage.
        mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ if read_only else mmap.ACCESS_COPY)
    state={}
    for name,entry in header.items():
        if name=='__metadata__':continue
        lo,hi=entry['data_offsets'];dtype=dtypes[entry['dtype']]
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='The given buffer is not writable')
            tensor=torch.frombuffer(mapping,dtype=dtype,count=(hi-lo)//dtype.itemsize,offset=base+lo).view(entry['shape']) if hi>lo else torch.empty(entry['shape'],dtype=dtype)
        # Explicit storage lifetime, including after the state-dict object is released.
        tensor.untyped_storage()._studio_h3_mapping=mapping
        state[name]=tensor
    return state,header.get('__metadata__')


def install(target, read_only=False):
    import torch
    import comfy.utils
    target=Path(target).resolve();original=comfy.utils.load_torch_file
    def selected_loader(ckpt,safe_load=False,device=None,return_metadata=False):
        if Path(ckpt).resolve()!=target or (device is not None and torch.device(device).type!='cpu'):
            return original(ckpt,safe_load=safe_load,device=device,return_metadata=return_metadata)
        state,metadata=load_cpu(target,torch,comfy.utils._TYPES,read_only)
        print('H3 loader experiment: '+target.name+', stdlib '+('read-only' if read_only else 'copy-on-write')+' mmap, '+str(len(state))+' CPU tensor views',flush=True)
        return (state,metadata) if return_metadata else state
    comfy.utils.load_torch_file=selected_loader
    return original
