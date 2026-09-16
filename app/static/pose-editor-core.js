/* Pure COCO-18 pose geometry for the Combine pose editor. Drawing a guide is not generating a picture. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudioPoseEditor=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  // OpenPose COCO-18 order, joint for joint with studio_workflow/pose_artifact.JOINTS: the endpoint reads this order.
  const JOINTS=['nose','neck','right_shoulder','right_elbow','right_wrist','left_shoulder','left_elbow','left_wrist','right_hip','right_knee',
                'right_ankle','left_hip','left_knee','left_ankle','right_eye','left_eye','right_ear','left_ear'];
  const LABELS=JOINTS.map(name=>name.replace(/_/g,' ').replace(/^./,c=>c.toUpperCase()));
  // studio_workflow/pose_raster.py: the same limb pairs and colours, and a limb takes its end joint's colour,
  // so the canvas shows what the server actually renders (at a thicker stroke: the guide uses min(w,h)//128).
  const LIMBS=[[1,2],[2,3],[3,4],[1,5],[5,6],[6,7],[1,8],[8,9],[9,10],[1,11],[11,12],[12,13],[1,0],[0,14],[14,16],[0,15],[15,17]];
  const COLORS=['#ff0000','#ff5500','#ffaa00','#ffff00','#aaff00','#55ff00','#00ff00','#00ff55','#00ffaa','#00ffff',
                '#00aaff','#0055ff','#0000ff','#5500ff','#aa00ff','#ff00ff','#ff00aa','#ff0055'];
  // Fractions of the canvas. Bent is the hand-estimated figure that carried the pose on 3 of 3 research seeds
  // (experiments/curated/style-pose-matrix/2026-09-14-combine/research-scripts/pose_sources.py, KP; its right ear is unknown).
  const BENT=[[.23,.31],[.34,.17],[.30,.14],[.27,.27],[.31,.31],[.42,.11],[.55,.05],[.44,.30],[.62,.30],[.49,.58],
              [.20,.84],[.81,.31],[.63,.62],[.68,.85],[.25,.28],[.21,.30],null,[.30,.23]];
  const STANDING=[[.50,.12],[.50,.19],[.42,.20],[.39,.31],[.37,.42],[.58,.20],[.61,.31],[.63,.42],[.45,.47],[.44,.66],
                  [.44,.86],[.55,.47],[.56,.66],[.56,.86],[.475,.108],[.525,.108],[.45,.12],[.55,.12]];
  const PRESETS=[{id:'standing',label:'Standing',points:STANDING},{id:'bent',label:'Bent forward, looking back',points:BENT},{id:'mirror',label:'Mirror left-right'}];

  function finite(value){return typeof value==='number'&&isFinite(value);}
  function canvasOf(canvas){
    const width=Number(canvas&&canvas.width),height=Number(canvas&&canvas.height);
    if(!finite(width)||!finite(height)||width<1||height<1)throw Error('A pose canvas needs a width and a height in pixels.');
    return{width:Math.round(width),height:Math.round(height)};
  }
  function at(points,index){return Array.isArray(points)&&Number.isInteger(index)&&index>=0&&index<JOINTS.length?points[index]||null:null;}
  function clamp(value,limit){return Math.min(limit,Math.max(0,value));}
  function place(x,y,canvas){return{x:clamp(x,canvas.width),y:clamp(y,canvas.height)};}
  function copy(points){return JOINTS.map((_,i)=>{const p=at(points,i);return p?{x:p.x,y:p.y}:null;});}
  function fromPreset(id,canvas){
    const c=canvasOf(canvas),found=PRESETS.find(item=>item.id===id&&item.points);
    return found?found.points.map(p=>p?place(p[0]*c.width,p[1]*c.height,c):null):null;
  }
  // A mirror is the same drawing seen the other way round: x flips about the canvas centre and each joint keeps
  // its own identity, because flipping a picture does not turn somebody's right wrist into their left one.
  function mirror(points,canvas){const c=canvasOf(canvas);return copy(points).map(p=>p?place(c.width-p.x,p.y,c):null);}
  function start(id,points,canvas){return id==='mirror'?mirror(points,canvas):fromPreset(id,canvas)||copy(points);}
  function move(points,index,x,y,canvas){
    const c=canvasOf(canvas),next=copy(points);
    if(!Number.isInteger(index)||index<0||index>=JOINTS.length||!finite(x)||!finite(y))return next;
    next[index]=place(x,y,c);return next;
  }
  // One arrow press moves a fraction of the canvas along that axis: 1 % plain, 5 % with Shift.
  function nudge(points,index,dx,dy,canvas,step){
    const c=canvasOf(canvas),joint=at(points,index);
    if(!joint||!finite(step))return copy(points);
    return move(points,index,joint.x+dx*step*c.width,joint.y+dy*step*c.height,c);
  }
  // A missing joint is not coordinate zero: it is omitted, and every limb touching it goes undrawn.
  function setUnknown(points,index){const next=copy(points);if(Number.isInteger(index)&&index>=0&&index<JOINTS.length)next[index]=null;return next;}
  function toggle(points,index,fallback,canvas){
    if(at(points,index))return setUnknown(points,index);
    const home=fallback&&finite(fallback.x)&&finite(fallback.y)?fallback:(fromPreset('standing',canvas)||[])[index];
    return home?move(points,index,home.x,home.y,canvas):copy(points);
  }
  function nearest(points,x,y,radius){
    let best=-1,closest=Number(radius)*Number(radius);
    JOINTS.forEach((_,i)=>{const p=at(points,i);if(!p)return;const distance=(p.x-x)*(p.x-x)+(p.y-y)*(p.y-y);if(distance<=closest){closest=distance;best=i;}});
    return best;
  }
  // The canvas controls can change under a drawn figure; the figure follows them instead of being thrown away.
  function resize(points,from,to){
    const a=canvasOf(from),b=canvasOf(to);
    return copy(points).map(p=>p?place(p.x/a.width*b.width,p.y/a.height*b.height,b):null);
  }
  function known(points){return copy(points).filter(Boolean).length;}
  function serialize(points,canvas){
    const c=canvasOf(canvas);
    if(!Array.isArray(points)||points.length!==JOINTS.length)throw Error('A pose carries exactly '+JOINTS.length+' joints.');
    const round=(value,limit)=>Math.round(clamp(value,limit)*100)/100;
    return{width:c.width,height:c.height,keypoints:copy(points).map(p=>p?[round(p.x,c.width),round(p.y,c.height)]:null)};
  }
  // Typed values are not pointer drags: refuse invalid/out-of-range input instead of clamping it.
  function positionInput(x,y,canvas){
    const c=canvasOf(canvas),fail=(axis,message)=>{const error=Error(message);error.axis=axis;throw error;},read=(value,axis)=>{
      if(typeof value!=='number'&&(typeof value!=='string'||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$/.test(value.trim())))
        fail(axis,'Enter X and Y as decimal pixel coordinates.');
      const result=Number(value);if(!Number.isFinite(result))fail(axis,'Coordinates must be finite.');return result;
    },point={x:read(x,'x'),y:read(y,'y')};
    if(point.x<0||point.x>c.width)fail('x','X must be 0–'+c.width+' and Y 0–'+c.height+' pixels.');
    if(point.y<0||point.y>c.height)fail('y','X must be 0–'+c.width+' and Y 0–'+c.height+' pixels.');
    return point;
  }
  // Treat rendering as a response to this exact canvas; never spread untrusted attachment metadata into a slot.
  function guideResponse(value,request){
    if(!value||typeof value!=='object'||Array.isArray(value)||!request
        ||typeof value.file!=='string'||typeof value.sha256!=='string'||typeof value.artifact_id!=='string'
        ||!/^[a-f0-9]{32}_drawn-pose\.png$/.test(value.file||'')
        ||!/^[a-f0-9]{64}$/.test(value.sha256||'')||!/^[a-f0-9]{64}$/.test(value.artifact_id||'')
        ||!Number.isInteger(value.bytes)||value.bytes<1||value.bytes>20*1024*1024
        ||value.width!==request.width||value.height!==request.height
        ||value.renderer!=='studio.coco18-lines/v1'||value.generation_submitted!==false)
      throw Error('The rendered guide did not match this drawing request. The previous picture was kept.');
    return Object.fromEntries(['file','sha256','artifact_id','bytes','width','height','renderer','generation_submitted'].map(key=>[key,value[key]]));
  }
  return{JOINTS,LABELS,LIMBS,COLORS,PRESETS,fromPreset,mirror,start,move,nudge,setUnknown,toggle,nearest,resize,known,serialize,guideResponse,positionInput};
});
