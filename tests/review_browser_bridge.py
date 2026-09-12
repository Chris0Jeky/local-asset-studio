"""Test-only UI transport for environments whose Chromium policy blocks localhost.

Routes requests through Python's real fixture HTTP server. Image/anchor shims are
explicit: this tests UI interactions, not native browser-to-Studio networking.
"""
import base64
import json
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlparse


def load_bridge(page,base,identifier):
    address=urlparse(base)
    def dispatch(path,options=None):
        if not isinstance(path,str) or not path.startswith('/api/production/'+identifier+'/') or '..' in path:raise ValueError('Unknown fixture path')
        options=options or {};body=options.get('body')
        connection=HTTPConnection(address.hostname,address.port,timeout=10)
        try:
            connection.request(options.get('method','GET'),path,body,{'Content-Type':'application/json','Origin':base})
            reply=connection.getresponse();data=reply.read()
            return {'status':reply.status,'type':reply.getheader('Content-Type'),'data':base64.b64encode(data).decode()}
        finally:connection.close()
    page.expose_function('__reviewTransport',dispatch)
    page.goto('about:blank?project='+identifier)
    root=Path(__file__).parents[1]/'app/static'
    html=(root/'review.html').read_text(encoding='utf-8').replace('<link rel="stylesheet" href="/review.css"><script defer src="/review.js"></script>','')
    page.set_content(html);page.add_style_tag(content=(root/'review.css').read_text(encoding='utf-8'))
    page.add_script_tag(content=r'''
      const decodeBytes=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
      window.fetch=async (path,options={})=>{
        const value=await window.__reviewTransport(path,options);
        return new Response(decodeBytes(value.data),{status:value.status,headers:{'Content-Type':value.type}});
      };
      const NativeImage=window.Image;
      window.Image=class extends NativeImage{
        set src(path){this.pending=window.__reviewTransport(path).then(value=>{if(value.status!==200)throw Error('Fixture image unavailable');super.src='data:'+value.type+';base64,'+value.data;return super.decode();});}
        decode(){return this.pending;}
      };
      document.addEventListener('click',event=>{
        const anchor=event.target.closest('a[download]');
        if(!anchor||!anchor.getAttribute('href').startsWith('/api/'))return;
        event.preventDefault();window.__reviewTransport(anchor.getAttribute('href')).then(value=>{
          const data=new Blob([decodeBytes(value.data)],{type:value.type});const link=document.createElement('a');
          link.href=URL.createObjectURL(data);link.download=anchor.getAttribute('href').split('/').pop().split('?')[0];link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
        });
      },true);
    ''')
    page.add_script_tag(content=(root/'review.js').read_text(encoding='utf-8'))
