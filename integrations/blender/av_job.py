"""Run only via a separate Blender process with --disable-autoexec.
A narrow starter, not a sandbox. No arbitrary Python operation from JSON.
Blender execution is pending; core JSON/path logic is independently tested.
"""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from studio_av.project import fields, number, read_json, safe_path, write_new, need

def validate_job(job,root):
    fields(job,['operation','report'],['frame','output'])
    need(job['operation'] in ('inspect_scene','render_frame','export_glb'),'Operation not allowed')
    safe_path(root,job['report'],False);need(job['report'].endswith('.json'),'Report must be JSON')
    if job['operation']=='render_frame':
        need('frame' in job and 'output' in job,'Frame/output required');number(job['frame'],0,100000,'frame',True)
        need(job['output'].endswith('.png'),'Render output must be PNG')
    elif job['operation']=='export_glb':need('output' in job and job['output'].endswith('.glb'),'GLB output required')
    if 'output' in job:
        path=safe_path(root,job['output'],False);need(not path.exists(),'Refuse existing output')
    need(not safe_path(root,job['report'],False).exists(),'Refuse existing report')
    return job

def run(job,root):
    import bpy
    validate_job(job,root);need(bpy.app.version>=(4,1,0),'Review an adapter for Blender older than4.1')
    scene=bpy.context.scene
    report={'blender_version':bpy.app.version_string,'operation':job['operation'],'source_blend':bpy.data.filepath,
        'objects':[{'name':o.name,'type':o.type,'dimensions':list(o.dimensions)} for o in scene.objects],
        'armatures':[{'name':a.name,'bones':[b.name for b in a.bones]} for a in bpy.data.armatures],
        'actions':[a.name for a in bpy.data.actions],
        'shape_keys':{m.name:[k.name for k in m.shape_keys.key_blocks] for m in bpy.data.meshes if m.shape_keys},
        'materials':[m.name for m in bpy.data.materials],'frame_range':[scene.frame_start,scene.frame_end],
        'creative_acceptance':'not_reviewed'}
    if job['operation']=='render_frame':
        need(scene.camera is not None,'Approved camera required')
        need(scene.render.resolution_x*scene.render.resolution_y*(scene.render.resolution_percentage/100)**2<=1920*1080,'Render pixel cap exceeded')
        scene.frame_set(job['frame']);scene.render.image_settings.file_format='PNG';scene.render.filepath=str(safe_path(root,job['output'],False));bpy.ops.render.render(write_still=True)
    elif job['operation']=='export_glb':
        bpy.ops.export_scene.gltf(filepath=str(safe_path(root,job['output'],False)),export_format='GLB',export_animations=True)
    write_new(safe_path(root,job['report'],False),report)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--job',required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(read_json(safe_path(args.workspace,args.job)),args.workspace)
