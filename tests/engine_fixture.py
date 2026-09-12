"""Original CPU-authored QA data, not generated art or a reviewed game asset."""
import hashlib
import json
import math
from pathlib import Path
import struct
from PIL import Image, ImageDraw


def glb_bytes(document, binary=b''):
    raw = json.dumps(document, separators=(',', ':'), allow_nan=False).encode()
    raw += b' ' * (-len(raw) % 4)
    body = struct.pack('<II', len(raw), 0x4e4f534a) + raw
    if binary:
        binary += b'\0' * (-len(binary) % 4)
        body += struct.pack('<II', len(binary), 0x004e4942) + binary
    return struct.pack('<4sII', b'glTF', 2, 12 + len(body)) + body


def model(skinned=False):
    binary = bytearray(); views = []; accessors = []
    def data(values, fmt, component, kind, count, **fields):
        binary.extend(b'\0' * (-len(binary) % 4)); start = len(binary)
        encoded = struct.pack('<' + fmt * len(values), *values); binary.extend(encoded)
        views.append({'buffer': 0, 'byteOffset': start, 'byteLength': len(encoded)})
        accessors.append({'bufferView': len(views)-1, 'componentType': component, 'count': count, 'type': kind, **fields})
        return len(accessors)-1
    pos = data([-.5,0,0,.5,0,0,0,1,0], 'f', 5126, 'VEC3', 3, min=[-.5,0,0], max=[.5,1,0])
    normal = data([0,0,1]*3, 'f', 5126, 'VEC3', 3)
    indices = data([0,1,2], 'H', 5123, 'SCALAR', 3)
    times = data([0,.24,.48], 'f', 5126, 'SCALAR', 3, min=[0], max=[.48])
    q = math.sqrt(.5)
    rotation = data([0,0,0,1,0,0,q,q,0,0,0,1], 'f', 5126, 'VEC4', 3)
    attributes = {'POSITION': pos, 'NORMAL': normal}
    nodes = [{'name':'FixtureRoot', 'translation':[1,2,3], 'children':[1]},
             {'name':'Hinge', 'translation':[0,.5,0], 'mesh':0}]
    doc = {'asset':{'version':'2.0','generator':'Local Asset Studio original engine QA fixture'},
           'scene':0,'scenes':[{'name':'EngineFixture','nodes':[0]}], 'nodes':nodes,
           'meshes':[{'name':'Panel','primitives':[{'attributes':attributes,'indices':indices,'material':0}]}],
           'materials':[{'name':'FixturePaint','pbrMetallicRoughness':{'baseColorFactor':[.2,.6,.8,1], 'metallicFactor':.2,'roughnessFactor':.7}}],
           'animations':[{'name':'HingeAction','samplers':[{'input':times,'output':rotation,'interpolation':'LINEAR'}],
                          'channels':[{'sampler':0,'target':{'node':1,'path':'rotation'}}]}]}
    if skinned:
        attributes['JOINTS_0'] = data([0,0,0,0]*3, 'H', 5123, 'VEC4', 3)
        attributes['WEIGHTS_0'] = data([1,0,0,0]*3, 'f', 5126, 'VEC4', 3)
        matrix = data([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1], 'f', 5126, 'MAT4', 1)
        nodes[0]['children'].append(2); nodes.append({'name':'RootJoint'}); nodes[1]['skin']=0
        doc['skins']=[{'name':'FixtureSkin','joints':[2],'skeleton':2,'inverseBindMatrices':matrix}]
        doc['animations'][0]['channels'][0]['target']['node']=2
    doc.update(buffers=[{'byteLength':len(binary)}], bufferViews=views, accessors=accessors)
    return doc, bytes(binary)


def create(root, *, loop=True, blank=False, skinned=False):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    with Image.new('RGBA', (256,64), (0,0,0,0)) as image:
        draw=ImageDraw.Draw(image)
        for i in range(4):
            if blank and i==1:continue
            draw.rectangle((i*64+20,12,i*64+43,55), fill=(50,140,210,255))
            draw.rectangle((i*64+26,4,i*64+37,16), fill=(240,190,90,255))
        image.save(root/'atlas.png')
    manifest={'schema_version':1,'kind':'sprite_atlas','clip':'idle-qa','loop':loop,
              'logical_canvas':[64,64],'anchor':[32,60], 'atlas':'atlas.png',
              'atlas_sha256':hashlib.sha256((root/'atlas.png').read_bytes()).hexdigest(), 'filter':'nearest',
              'frames':[{'id':f'frame-{i}','region':[i*64,0,64,64],'duration_ms':ms}
                        for i,ms in enumerate((120,80,120,160))]}
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    doc,binary=model(skinned)
    (root/'fixture.glb').write_bytes(glb_bytes(doc,binary))
    return manifest
