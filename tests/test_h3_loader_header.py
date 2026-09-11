import io
import json
from pathlib import Path
import struct
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from h3_mmap_loader import checked_header
from game_asset_pipeline import graph_check


class LoaderAndSchemaTests(unittest.TestCase):
    def test_header_rejects_overlap_and_incomplete_extent(self):
        types={'U8':SimpleNamespace(itemsize=1)}
        def check(header,payload=8):
            raw=json.dumps(header).encode();blob=struct.pack('<Q',len(raw))+raw+b'\0'*payload
            return checked_header(io.BytesIO(blob),len(blob),types)
        base={'a':{'dtype':'U8','shape':[4],'data_offsets':[0,4]},'b':{'dtype':'U8','shape':[4],'data_offsets':[4,8]}}
        self.assertEqual(check(base)[0],base)
        base['b']['data_offsets']=[2,6]
        with self.assertRaisesRegex(ValueError,'Overlapping'):check(base)
        base['b']['data_offsets']=[4,9]
        with self.assertRaisesRegex(ValueError,'extent'):check(base)

    def test_dynamic_reference_only_accepts_dotted_selected_branch(self):
        info={'Image':{'input':{'required':{}},'output':['IMAGE']},'Edit':{'input':{'required':{'image':['COMFY_DYNAMICCOMBO_V3',{'options':[{'key':'0','inputs':{'required':{}}},{'key':'1','inputs':{'required':{'image_1':['IMAGE']}}}]}]}},'output':['IMAGE']}}
        graph={'1':{'class_type':'Image','inputs':{}},'2':{'class_type':'Edit','inputs':{'image':'1','image.image_1':['1',0]}}}
        self.assertTrue(graph_check(graph,info)['node_snapshot_checked'])
        graph['2']['inputs']['image']='0'
        with self.assertRaisesRegex(ValueError,'Unknown input'):graph_check(graph,info)
        graph['2']['inputs']={'image':'2'}
        with self.assertRaisesRegex(ValueError,'Unknown dynamic'):graph_check(graph,info)
