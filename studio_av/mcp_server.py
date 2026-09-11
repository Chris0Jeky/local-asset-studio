"""Optional official MCP SDK 2.2 stdio adapter. Core module imports without MCP."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import uuid
from .project import read_json, safe_path, validate, edit, digest, need
from .render import compile_project, inspect_wav, render

def build_server(workspace, allow_render=False):
    from mcp.server import MCPServer
    root=Path(workspace).resolve();need(root.is_dir(),'Workspace must exist')
    server=MCPServer('Local Asset Studio AV',instructions='Read capabilities and validate the exact project before edits or rendering. No arbitrary commands, model generation or network media. Render is optional and may be absent.')
    @server.tool()
    def capabilities() -> dict:
        """List implemented operations and exact limitations, not research promises."""
        return {'schema':1,'render_enabled':allow_render,'operations':['validate','plan','propose_edit','audio_qc']+(['render_preview'] if allow_render else []),'model_inference':False,'blender_connected':False,'caps':{'duration_seconds':120,'shots':16,'audio_clips':32},'unsupported':['TTS','GPU generation','live DAW','VST','HDR','retargeting']}
    @server.tool()
    def validate_project(project_path: str) -> dict:
        """Read workspace-relative JSON and verify file hashes, schema, bounds and timing."""
        return validate(read_json(safe_path(root,project_path)),root)
    @server.tool()
    def plan_preview(project_path: str) -> dict:
        """Compile a bounded FFmpeg plan without executing or writing anything."""
        return compile_project(read_json(safe_path(root,project_path)),root)
    @server.tool()
    def propose_edit(project_path: str, expected_revision: str, section: str, clip_id: str, field: str, value_json: str) -> dict:
        """Return a new validated project and reversible edit; no write, render or side effects."""
        need(len(value_json)<=100,'Edit value too large')
        project=read_json(safe_path(root,project_path));validate(project,root)
        return edit(project,expected_revision,section,clip_id,field,json.loads(value_json))
    @server.tool()
    def audio_qc(audio_path: str) -> dict:
        """Measure 16bit PCM WAV peak/RMS/DC; not LUFS, voice quality or true peak."""
        return inspect_wav(safe_path(root,audio_path))
    if allow_render:
        @server.tool()
        def render_preview(project_path: str, expected_revision: str) -> dict:
            """Explicitly render local CPU preview. New immutable folder; may take time. No GPU or paid calls."""
            project=read_json(safe_path(root,project_path));need(digest(project)==expected_revision,'Stale revision')
            relative='renders/av-'+uuid.uuid4().hex
            out=safe_path(root,relative,False)
            receipt=render(project,root,out)
            return {'output_directory':relative,'receipt':receipt}
    return server

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True);parser.add_argument('--allow-render',action='store_true');args=parser.parse_args()
    build_server(args.workspace,args.allow_render).run(transport='stdio')
if __name__=='__main__':main()
