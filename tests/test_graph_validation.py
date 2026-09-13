"""Source-derived schema contracts, not native execution or an installed-node capture."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import game_asset_pipeline as pipeline
INFO = json.loads((ROOT/'tests/fixtures/graph-validation/object-info.json').read_text())


def video(**inputs):
    return {'source':{'class_type':'FixtureSources','inputs':{}},
            'save':{'class_type':'SaveVideo','inputs':{'video':['source',0], 'filename_prefix':'fixture', **inputs}}}


def literal(descriptor, value):
    graph={'1':{'class_type':'Widget','inputs':{'value':value}}}
    info={'Widget':{'input':{'required':{'value':descriptor}},'output':[]}}
    return graph,info


class GraphValidationTests(unittest.TestCase):
    def test_mesh_and_file_can_connect_to_declared_union(self):
        for slot in (1,4):
            graph={'source':{'class_type':'FixtureSources','inputs':{}},
                   'save':{'class_type':'SaveGLB','inputs':{'mesh':['source',slot],'filename_prefix':'test'}}}
            with self.subTest(slot=slot):self.assertFalse(pipeline.graph_check(graph,INFO)['inference_verified'])

    def test_unions_trim_whitespace_and_accept_overlap_not_disjoint_types(self):
        for received,expected in [('MESH','FILE_3D_GLB, MESH'),('IMAGE,MASK','MASK,VIDEO'),('*','MESH'),('MESH','*')]:
            graph,info=literal([expected],['source',0])
            graph['source']={'class_type':'Source','inputs':{}}
            info['Source']={'input':{},'output':[received]}
            with self.subTest(received=received,expected=expected):pipeline.graph_check(graph,info)
        for received,expected in [('IMAGE','MESH'),('IMAGE,','IMAGE'),('', '*'),(['MESH'],'MESH')]:
            graph,info=literal([expected],['source',0]);graph['source']={'class_type':'Source','inputs':{}}
            info['Source']={'input':{},'output':[received]}
            with self.subTest(received=received),self.assertRaisesRegex(ValueError,'type mismatch'):pipeline.graph_check(graph,info)

    def test_legacy_flat_video_codec_is_valid_without_dotted_codec(self):
        pipeline.graph_check(video(format='auto',codec='auto'),INFO)
        pipeline.graph_check(video(format='mp4',codec='h264'),INFO)

    def test_nested_codec_and_optional_encoding_are_valid(self):
        for inputs in ({'format':'mp4','format.codec':'h264'},
                       {'format':'webm','format.codec':'av1','format.codec.encoding':'auto'},
                       {'format':'mp4','format.codec':'h264','format.codec.encoding':'re-encode','format.codec.encoding.crf':23.0},
                       {'format':'mp4','codec':'h264','codec.encoding':'re-encode','codec.encoding.crf':12}):
            with self.subTest(inputs=inputs):pipeline.graph_check(video(**inputs),INFO)

    def test_absent_dynamic_selectors_do_not_expand_or_pick_defaults(self):
        graph=video(format='mp4');before=copy.deepcopy(graph)
        fields,required=pipeline.expanded_input_contract(INFO['SaveVideo'],graph['save']['inputs'])
        self.assertNotIn('format.codec',fields);self.assertNotIn('codec',fields)
        self.assertEqual(required,{'video','filename_prefix','format'})
        pipeline.graph_check(graph,INFO);self.assertEqual(graph,before)
        # Native V3 expansion omits even an absent root selector. Static compatibility
        # does not assert that SaveVideo.execute will accept a missing Python argument.
        pipeline.graph_check(video(),INFO)

    def test_missing_ordinary_required_field_remains_an_error(self):
        graph=video(format='auto');del graph['save']['inputs']['video']
        with self.assertRaisesRegex(ValueError,'Missing required input: video'):pipeline.graph_check(graph,INFO)

    def test_selected_branch_requires_its_scalar_fields(self):
        graph=video(**{'format':'mp4','format.codec':'h264','format.codec.encoding':'re-encode'})
        with self.assertRaisesRegex(ValueError,'format.codec.encoding.crf'):pipeline.graph_check(graph,INFO)

    def test_unknown_dynamic_option_is_not_treated_as_absent(self):
        for inputs in ({'format':'invented'},{'format':'webm','format.codec':'h264'},
                       {'format':'mp4','codec':'bogus'},{'format':'mp4','format.codec':'av1','format.codec.encoding':'bad'}):
            with self.subTest(inputs=inputs),self.assertRaisesRegex(ValueError,'Unknown dynamic input option'):pipeline.graph_check(video(**inputs),INFO)

    def test_inactive_or_unselected_dotted_fields_are_not_dropped(self):
        for inputs in ({'format':'auto','format.codec.encoding.crf':23},
                       {'format':'mp4','format.codec':'auto','format.codec.encoding':'auto'},
                       {'codec.encoding':'auto'}, {'prompt':'untrusted hidden input'}):
            with self.subTest(inputs=inputs),self.assertRaisesRegex(ValueError,'Unknown input'):pipeline.graph_check(video(**inputs),INFO)

    def test_both_native_and_legacy_selected_codecs_are_checked(self):
        pipeline.graph_check(video(**{'format':'mp4','format.codec':'auto','codec':'av1'}),INFO)
        with self.assertRaisesRegex(ValueError,'Unknown dynamic'):pipeline.graph_check(video(**{'format':'mp4','format.codec':'auto','codec':'bad'}),INFO)

    def test_native_branch_ranges_and_scalar_types_remain_enforced(self):
        for crf in (-1,52,True,'23',float('inf')):
            with self.subTest(crf=crf),self.assertRaises(ValueError):
                pipeline.graph_check(video(**{'format':'mp4','format.codec':'h264','format.codec.encoding':'re-encode','format.codec.encoding.crf':crf}),INFO)

    def test_malformed_dynamic_descriptors_fail_usefully(self):
        for spec in ([],['COMFY_DYNAMICCOMBO_V3'],['COMFY_DYNAMICCOMBO_V3',{}],
                     ['COMFY_DYNAMICCOMBO_V3',{'options':[]}],
                     ['COMFY_DYNAMICCOMBO_V3',{'options':[{'key':'x','inputs':None}]}],
                     ['COMFY_DYNAMICCOMBO_V3',{'options':[{'key':'x','inputs':{}},{'key':'x','inputs':{}}]}]):
            graph,info=literal(spec,'x')
            with self.subTest(spec=spec),self.assertRaises(ValueError):pipeline.graph_check(graph,info)

    def test_dynamic_expansion_depth_is_bounded(self):
        child={}
        for _ in range(10):child={'required':{'choice':['COMFY_DYNAMICCOMBO_V3',{'options':[{'key':'x','inputs':child}]}]}}
        info={'Nested':{'input':child,'output':[]}}
        graph={'1':{'class_type':'Nested','inputs':{'.'.join(['choice']*n):'x' for n in range(1,11)}}}
        with self.assertRaisesRegex(ValueError,'eight levels'):pipeline.graph_check(graph,info)

    def test_color_widget_literal_is_accepted_without_executing_widget_code(self):
        descriptor=INFO['ImageCropToMask']['input']['required']['background']
        graph,info=literal(descriptor,'#000000');before=copy.deepcopy((graph,info))
        pipeline.graph_check(graph,info);self.assertEqual((graph,info),before)
        for value in (False,1,{},None):
            with self.subTest(value=value),self.assertRaises(ValueError):pipeline.graph_check(*literal(descriptor,value))

    def test_socketless_does_not_authorize_links(self):
        graph,info=literal(['COLOR',{'socketless':True,'default':'#000000'}],['s',0])
        graph['s']={'class_type':'Source','inputs':{}};info['Source']={'input':{},'output':['COLOR']}
        with self.assertRaisesRegex(ValueError,'Socketless'):pipeline.graph_check(graph,info)

    def test_default_on_opaque_socket_does_not_authorize_literal(self):
        for descriptor in (['MODEL',{'default':'model'}],['MODEL'],['COLOR',{'socketless':True}],
                           ['COLOR',{'socketless':'true','default':'#000000'}]):
            with self.subTest(descriptor=descriptor),self.assertRaisesRegex(ValueError,'Opaque input'):pipeline.graph_check(*literal(descriptor,'model'))

    def test_custom_numeric_widget_accepts_only_default_scalar_shape(self):
        pipeline.graph_check(*literal(['CUSTOM',{'socketless':True,'default':1.0}],2))
        with self.assertRaisesRegex(ValueError,'Widget literal type mismatch'):pipeline.graph_check(*literal(['CUSTOM',{'socketless':True,'default':1}],True))
        with self.assertRaisesRegex(ValueError,'Invalid widget default'):pipeline.graph_check(*literal(['CUSTOM',{'socketless':True,'default':float('nan')}],1.0))

    def test_existing_scalar_enum_and_int64_contracts_preserved(self):
        pipeline.graph_check(*literal(['INT',{'min':0,'max':2**64-1}],2**64-1))
        pipeline.graph_check(*literal(['INT',{'max':10**400}],7))
        pipeline.graph_check(*literal([['a','b']],'a'))
        pipeline.graph_check(*literal(['COMBO',{'options':['a','b']}],'b'))
        for desc,value in ((['INT'],True),(['FLOAT'],'1'),(['BOOLEAN'],1),(['STRING'],False),
                           (['COMBO',{}],'a'),(['INT',{'max':float('inf')}],2),([['a']],'b')):
            with self.subTest(desc=desc,value=value),self.assertRaises(ValueError):pipeline.graph_check(*literal(desc,value))

    def test_links_cycles_and_malformed_source_contracts_still_fail(self):
        for link in (['missing',0],['s',-1],['s',True],['s',2],['s',0,1]):
            graph,info=literal(['IMAGE'],link);graph['s']={'class_type':'Source','inputs':{}}
            info['Source']={'input':{},'output':['IMAGE']}
            with self.subTest(link=link),self.assertRaises(ValueError):pipeline.graph_check(graph,info)
        with self.assertRaisesRegex(ValueError,'cycle'):pipeline.graph_check({'1':{'class_type':'Source','inputs':{'image':['1',0]}}})
        graph,info=literal(['IMAGE'],['s',0]);graph['s']={'class_type':'Source','inputs':{}}
        for source in (None,{'input':{},'output':'IMAGE'}):
            info['Source']=source
            with self.subTest(source=source),self.assertRaises(ValueError):pipeline.graph_check(graph,info)

    def test_incomplete_node_schema_cannot_certify_a_graph(self):
        graph={'1':{'class_type':'Node','inputs':{}}}
        for schema in ({'output':[]},{'input':{},'output':None},{'input':{}}):
            with self.subTest(schema=schema),self.assertRaisesRegex(ValueError,'Invalid node (input|output) contract'):
                pipeline.graph_check(graph,{'Node':schema})

    def test_diagnostics_name_node_class_and_field(self):
        with self.assertRaisesRegex(ValueError,r'Node save \(SaveVideo\): Unknown dynamic input option: format'):
            pipeline.graph_check(video(format='bad'),INFO)

    def test_structural_mode_is_still_available_and_explicitly_not_inference(self):
        result=pipeline.graph_check(video(format='not-a-real-selection'))
        self.assertFalse(result['node_snapshot_checked']);self.assertFalse(result['inference_verified'])
        with self.assertRaises(ValueError):pipeline.graph_check(video(format='auto'),[])


if __name__=='__main__':unittest.main()
