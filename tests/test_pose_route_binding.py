import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_artifact, pose_raster, pose_route_binding as binding


def digest(char): return char * 64


def artifact(width=256, height=256, missing=()):
    points=[]
    for index in range(18):
        if pose_artifact.JOINTS[index] in missing:
            points.extend([0,0,0])
        else:
            points.extend([20 + (index % 6) * 35, 20 + (index // 6) * 90, .9])
    raw=json.dumps({'people':[{'pose_keypoints_2d':points}]}).encode()
    return pose_artifact.import_openpose(raw,width=width,height=height,coordinate_space='pixels')


def pins(route_id):
    values={key:digest(char) for key,char in (
        ('model','1'),('encoder','2'),('vae','3'),('graph','4'),('nodes','5'),
        ('runtime','6'),('reference_transform','7'),('prompt_dialect','8'))}
    if route_id=='copy-pose': values['lora']=digest('9')
    elif route_id=='klein-geometry': values['renderer']=digest('a')
    else: values.update(controlnet=digest('b'),renderer=digest('c'))
    return values


def transform(source,target,kind='identity'):
    return binding.expected_transform(kind,source,target)


def skeleton_request(pose,data,route_id='sdxl-corrected-skeleton',target=None,renderer_id=pose_raster.RENDERER):
    canvas=pose['canvas']; target=target or canvas
    if route_id=='sdxl-corrected-skeleton':
        mechanism='sdxl-precomputed-skeleton'; detector='bypass-precomputed-guide'; slot='control-image'
    else:
        mechanism='klein-geometry-reference'; detector='not-applicable'; slot='geometry-reference'
    threshold=.3
    filtered=[]
    for name in pose_artifact.JOINTS:
        point=pose['joints'][name]
        if point is None or (point['origin']=='estimated' and point['confidence']<threshold): filtered.append(name)
    return {
        'schema':binding.REQUEST_SCHEMA,'authority':'none','execution_authorized':False,'generation_submitted':False,
        'binding_name':'synthetic-pose-binding',
        'route':{'id':route_id,'mechanism':mechanism,'source_kind':'precomputed-skeleton',
                 'detector_behavior':detector,'native_slot':slot,'backend_id':'primary',
                 'target_canvas':target,'pins':pins(route_id)},
        'source':{'kind':'precomputed-skeleton','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
                  'format':'PNG','canvas':canvas,'artifact_id':pose['id'],'renderer_id':renderer_id,
                  'renderer_sha256':pins(route_id)['renderer'],'threshold':threshold,'expected_filtered_joints':filtered},
        'transform':transform(canvas,target,'identity' if canvas==target else 'contain-pad'),
    }


def rgb_bytes(width=320,height=240,fmt='PNG',mode='RGB'):
    image=Image.new(mode,(width,height),(90,100,110,255) if mode=='RGBA' else (90,100,110))
    out=io.BytesIO(); image.save(out,format=fmt); image.close(); return out.getvalue()


def copy_request(data,width=320,height=240,target=None,fmt='PNG'):
    source={'width':width,'height':height}; target=target or source
    return {
        'schema':binding.REQUEST_SCHEMA,'authority':'none','execution_authorized':False,'generation_submitted':False,
        'binding_name':'synthetic-copy-pose-binding',
        'route':{'id':'copy-pose','mechanism':'copy-pose-rgb','source_kind':'rgb-pose-donor',
                 'detector_behavior':'not-applicable','native_slot':'pose-donor-image-2','backend_id':'primary',
                 'target_canvas':target,'pins':pins('copy-pose')},
        'source':{'kind':'rgb-pose-donor','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
                  'format':fmt,'canvas':source},
        'transform':transform(source,target,'identity' if source==target else 'contain-pad'),
    }


class PoseRouteBindingTests(unittest.TestCase):
    def test_sdxl_precomputed_skeleton_recomputes_local_renderer_without_detector(self):
        pose=artifact(missing=('right_ear',)); data=pose_raster.render_png(pose,.3); req=skeleton_request(pose,data)
        result=binding.compile_binding(req,data,artifact=pose)
        self.assertEqual(result['schema'],binding.BINDING_SCHEMA)
        self.assertEqual(result['route']['native_slot'],'control-image')
        self.assertEqual(result['diagnostics']['detector_invocations'],0)
        self.assertEqual(result['diagnostics']['renderer_validation'],'recomputed-exact')
        self.assertIn('right_ear',result['diagnostics']['filtered_joints'])
        self.assertGreater(result['diagnostics']['drawable_limbs'],0)
        self.assertGreater(result['diagnostics']['non_black_pixels'],0)
        self.assertFalse(result['ready_for_execution'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['generation_submitted'])
        self.assertRegex(result['binding_id'],r'^[0-9a-f]{64}$')

    def test_klein_external_renderer_is_receipt_bound_but_not_qualified(self):
        pose=artifact(); data=pose_raster.render_png(pose); req=skeleton_request(pose,data,'klein-geometry',renderer_id='installed-aux-renderer')
        result=binding.compile_binding(req,data,artifact=pose)
        self.assertEqual(result['route']['native_slot'],'geometry-reference')
        self.assertEqual(result['diagnostics']['renderer_validation'],'receipt-bound-not-recomputed')
        self.assertFalse(result['diagnostics']['route_qualified'])

    def test_copy_pose_binds_rgb_donor_to_exact_second_slot_without_artifact(self):
        data=rgb_bytes(); req=copy_request(data)
        result=binding.compile_binding(req,data)
        self.assertEqual(result['source']['kind'],'rgb-pose-donor')
        self.assertEqual(result['route']['native_slot'],'pose-donor-image-2')
        self.assertEqual(result['diagnostics']['renderer_validation'],'not-applicable')
        self.assertIsNone(result['diagnostics']['drawable_limbs'])
        self.assertEqual(result['diagnostics']['detector_invocations'],0)

    def test_transform_is_deterministic_for_identity_and_contain_pad(self):
        self.assertEqual(binding.expected_transform('identity',{'width':10,'height':20},{'width':10,'height':20}),{
            'kind':'identity','source_canvas':{'width':10,'height':20},'target_canvas':{'width':10,'height':20},
            'scaled_canvas':{'width':10,'height':20},'pad':{'left':0,'top':0,'right':0,'bottom':0}})
        self.assertEqual(binding.expected_transform('contain-pad',{'width':320,'height':240},{'width':512,'height':512}),{
            'kind':'contain-pad','source_canvas':{'width':320,'height':240},'target_canvas':{'width':512,'height':512},
            'scaled_canvas':{'width':512,'height':384},'pad':{'left':0,'top':64,'right':0,'bottom':64}})
        data=rgb_bytes(); req=copy_request(data,target={'width':512,'height':512})
        self.assertEqual(binding.compile_binding(req,data)['transform']['pad']['top'],64)

    def test_rejects_wrong_route_semantics_slots_and_detector_reentry(self):
        pose=artifact(); data=pose_raster.render_png(pose)
        mutations=(
            ('id','copy-pose'),('mechanism','copy-pose-rgb'),('source_kind','rgb-pose-donor'),
            ('detector_behavior','route-native'),('native_slot','pose-donor-image-2'))
        for field,value in mutations:
            req=skeleton_request(pose,data); req['route'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)

    def test_rejects_missing_extra_or_invalid_route_pins(self):
        pose=artifact(); data=pose_raster.render_png(pose)
        variants=[]
        req=skeleton_request(pose,data); del req['route']['pins']['controlnet']; variants.append(req)
        req=skeleton_request(pose,data); req['route']['pins']['extra']=digest('e'); variants.append(req)
        req=skeleton_request(pose,data); req['route']['pins']['renderer']='bad'; variants.append(req)
        req=skeleton_request(pose,data); req['source']['renderer_sha256']=digest('f'); variants.append(req)
        req=skeleton_request(pose,data); req['route']['backend_id']=''; variants.append(req)
        for req in variants:
            with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)

    def test_rejects_changed_bytes_hash_size_format_mode_canvas_animation_or_blank(self):
        pose=artifact(); data=pose_raster.render_png(pose)
        req=skeleton_request(pose,data)
        with self.assertRaises(ValueError): binding.compile_binding(req,data+b'x',artifact=pose)
        req=skeleton_request(pose,data); req['source']['bytes']+=1
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)
        req=skeleton_request(pose,data); req['source']['format']='JPEG'
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)
        donor=rgb_bytes(fmt='PNG'); req=copy_request(donor,fmt='JPEG')
        with self.assertRaises(ValueError): binding.compile_binding(req,donor)
        gray=Image.new('L',(256,256),255); out=io.BytesIO(); gray.save(out,format='PNG'); gray.close(); gray_data=out.getvalue()
        req=skeleton_request(pose,gray_data,renderer_id='external')
        with self.assertRaises(ValueError): binding.compile_binding(req,gray_data,artifact=pose)
        req=skeleton_request(pose,data); req['source']['canvas']['width']=255
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)
        frames=[Image.new('RGB',(32,32),(1,2,3)),Image.new('RGB',(32,32),(4,5,6))]; out=io.BytesIO(); frames[0].save(out,format='GIF',save_all=True,append_images=frames[1:]); [x.close() for x in frames]
        gif=out.getvalue(); req=copy_request(gif,32,32,fmt='PNG')
        with self.assertRaises(ValueError): binding.compile_binding(req,gif)
        blank=Image.new('RGB',(256,256),(0,0,0)); out=io.BytesIO(); blank.save(out,format='PNG'); blank.close(); blank_data=out.getvalue()
        req=skeleton_request(pose,blank_data,renderer_id='external')
        with self.assertRaises(ValueError): binding.compile_binding(req,blank_data,artifact=pose)

    def test_local_renderer_requires_exact_artifact_bytes(self):
        pose=artifact(); data=pose_raster.render_png(pose); req=skeleton_request(pose,data)
        image=Image.open(io.BytesIO(data)); changed=image.copy(); image.close(); changed.putpixel((0,0),(255,255,255)); out=io.BytesIO(); changed.save(out,format='PNG'); changed.close(); changed_data=out.getvalue()
        req['source']['sha256']=hashlib.sha256(changed_data).hexdigest(); req['source']['bytes']=len(changed_data)
        with self.assertRaisesRegex(ValueError,'local preview renderer'):
            binding.compile_binding(req,changed_data,artifact=pose)

    def test_rejects_artifact_identity_canvas_filter_and_drawable_limb_drift(self):
        pose=artifact(missing=('right_ear',)); data=pose_raster.render_png(pose); req=skeleton_request(pose,data)
        req['source']['artifact_id']=digest('f')
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)
        req=skeleton_request(pose,data); req['source']['expected_filtered_joints']=[]
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)
        changed=copy.deepcopy(pose); changed['canvas']['width']=255
        with self.assertRaises(ValueError): binding.compile_binding(skeleton_request(pose,data),data,artifact=changed)
        sparse=artifact(missing=tuple(pose_artifact.JOINTS[1:])); sparse_data=pose_raster.render_png(sparse); req=skeleton_request(sparse,sparse_data)
        with self.assertRaisesRegex(ValueError,'no drawable limb'): binding.compile_binding(req,sparse_data,artifact=sparse)

    def test_rejects_artifact_on_copy_pose_and_missing_artifact_on_skeleton(self):
        pose=artifact(); skeleton=pose_raster.render_png(pose)
        with self.assertRaises(ValueError): binding.compile_binding(skeleton_request(pose,skeleton),skeleton)
        data=rgb_bytes(); req=copy_request(data)
        with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)

    def test_rejects_inconsistent_transform_declarations(self):
        data=rgb_bytes(); req=copy_request(data,target={'width':512,'height':512})
        for mutate in (
            lambda r:r['transform']['pad'].__setitem__('top',63),
            lambda r:r['transform']['scaled_canvas'].__setitem__('height',383),
            lambda r:r['transform']['source_canvas'].__setitem__('width',319),
            lambda r:r.__setitem__('transform',{**r['transform'],'kind':'identity'}),
        ):
            bad=copy.deepcopy(req); mutate(bad)
            with self.assertRaises(ValueError): binding.compile_binding(bad,data)

    def test_binding_is_deterministic_and_tamper_evident(self):
        pose=artifact(); data=pose_raster.render_png(pose); req=skeleton_request(pose,data)
        first=binding.compile_binding(req,data,artifact=pose); second=binding.compile_binding(copy.deepcopy(req),data,artifact=copy.deepcopy(pose))
        self.assertEqual(first,second); self.assertEqual(binding.validate_binding(first,req,data,artifact=pose),first)
        tampered=copy.deepcopy(first); tampered['diagnostics']['detector_invocations']=1
        with self.assertRaises(ValueError): binding.validate_binding(tampered,req,data,artifact=pose)

    def test_zero_authority_and_unknown_fields_fail_closed(self):
        pose=artifact(); data=pose_raster.render_png(pose)
        variants=[]
        for key,value in (('authority','execute'),('execution_authorized',True),('generation_submitted',True),('schema','v2')):
            req=skeleton_request(pose,data); req[key]=value; variants.append(req)
        req=skeleton_request(pose,data); req['unknown']=1; variants.append(req)
        req=skeleton_request(pose,data); req['source']['unknown']=1; variants.append(req)
        for req in variants:
            with self.assertRaises(ValueError): binding.compile_binding(req,data,artifact=pose)


if __name__=='__main__': unittest.main()
