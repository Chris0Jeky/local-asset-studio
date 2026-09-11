import bpy,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent; (OUT/'renders').mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(OUT/'source-lantern.blend'))
s=bpy.context.scene;s.render.resolution_x=s.render.resolution_y=128;s.cycles.samples=16
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='HIP';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='HIP'
s.cycles.device='GPU'
meshes=[o for o in s.objects if o.type=='MESH'];bpy.ops.object.empty_add();rig=bpy.context.object;rig.name='Lantern bob rig'
for o in meshes:o.parent=rig
s.frame_start=1;s.frame_end=24;s.render.fps=12
for frame,height in [(1,0),(7,.08),(13,0),(19,-.08),(25,0)]:rig.location.z=height;rig.keyframe_insert(data_path='location',frame=frame)
variants={'moss':(.025,.28,.25),'amethyst':(.24,.035,.42),'ember':(.55,.10,.025)}
for skin,color in variants.items():
 material=bpy.data.materials['Deep teal enamel'];material.diffuse_color=(*color,1);material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
 for o in meshes:o.select_set(True)
 bpy.ops.export_scene.gltf(filepath=str(OUT/f'{skin}.glb'),use_selection=True,export_format='GLB',export_animations=True)
 for direction in range(8):
  a=math.tau*direction/8;s.camera.location=(4*math.sin(a),-4*math.cos(a),2.4);s.camera.rotation_euler=(Vector((0,0,.75))-s.camera.location).to_track_quat('-Z','Y').to_euler()
  for phase,frame in enumerate([1,7,13,19]):
   s.frame_set(frame);s.render.filepath=str(OUT/'renders'/f'{skin}-{direction}-{phase}.png');bpy.ops.render.render(write_still=True)
s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'lanternkeeper.blend'))
print('PACK_RENDER_COMPLETE',flush=True)
