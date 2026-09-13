'use strict';
const nodes={
 '1':{class_type:'CheckpointLoaderSimple',inputs:{ckpt_name:'base.safetensors'}},
 '2':{class_type:'CLIPTextEncode',inputs:{clip:['1',1],text:'Original idea'}},
 '3':{class_type:'CLIPTextEncode',inputs:{clip:['1',1],text:'blur'}},
 '4':{class_type:'LoraLoader',inputs:{model:['1',0],clip:['1',1],lora_name:'style.safetensors',strength_model:1,strength_clip:1}},
 '5':{class_type:'EmptyLatentImage',inputs:{width:768,height:1152,batch_size:1}},
 '6':{class_type:'KSampler',inputs:{model:['4',0],positive:['2',0],negative:['3',0],latent_image:['5',0],seed:123,steps:30,cfg:4,sampler_name:'euler',scheduler:'simple',denoise:1}},
 '7':{class_type:'VAEDecode',inputs:{samples:['6',0],vae:['1',2]}},
 '8':{class_type:'SaveImage',inputs:{images:['7',0],filename_prefix:'Studio/Fixture'}}};
const preset={id:'paint',name:'Illustration',family:'Synthetic',modality:'image',positive:['2','text'],negative:['3','text'],lora_name:['4','lora_name'],lora:['4','strength_model'],bindings_extra:{lora:[['4','strength_clip']]},width:['5','width'],height:['5','height'],seed:['6','seed'],steps:['6','steps'],cfg:['6','cfg'],sampler:['6','sampler_name'],scheduler:['6','scheduler'],denoise:['6','denoise'],defaults:{positive:'Original idea',negative:'blur',lora_name:'style.safetensors',lora:1,width:768,height:1152,seed:123,steps:30,cfg:4,sampler:'euler',scheduler:'simple',denoise:1}};
const base={format:'studio.workflow/v1',name:'Illustration',revision:0,backend_id:'primary',schema_sha256:'a'.repeat(64),nodes,outputs:['8'],disabled:[],bypass:{},positions:{},source:{preset_id:'paint',authoring_only:true}};
const snapshot={preset,recipe:{id:'painted',preset_id:'paint',name:'Painterly study'},graph:nodes,controls:{...preset.defaults,positive:'A cartographer holding an ornate lantern',lora:0.7,steps:24}};
module.exports={base,snapshot};
