"""Optional official MCP SDK 2.2 stdio adapter. Core module imports without MCP."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import uuid
from typing import Any
from .project import read_json, safe_path, validate, edit, digest, need
from .render import compile_project, inspect_wav, render
from .client import StudioClient

def build_workspace_server(workspace, allow_render=False):
    from mcp.server import MCPServer
    root=Path(workspace).resolve();need(root.is_dir(),'Workspace must exist')
    server=MCPServer('Local Asset Studio AV',instructions='Read capabilities and validate the exact project before edits or rendering. No arbitrary commands, model generation or network media. Render is optional and may be absent.')
    @server.tool(structured_output=True)
    def capabilities() -> dict[str, Any]:
        """List implemented operations and exact limitations, not research promises."""
        return {'schema':1,'render_enabled':allow_render,'operations':['validate','plan','propose_edit','audio_qc']+(['render_preview'] if allow_render else []),'model_inference':False,'blender_connected':False,'caps':{'duration_seconds':120,'shots':16,'audio_clips':32},'unsupported':['TTS','GPU generation','live DAW','VST','HDR','retargeting']}
    @server.tool(structured_output=True)
    def validate_project(project_path: str) -> dict[str, Any]:
        """Read workspace-relative JSON and verify file hashes, schema, bounds and timing."""
        return validate(read_json(safe_path(root,project_path)),root)
    @server.tool(structured_output=True)
    def plan_preview(project_path: str) -> dict[str, Any]:
        """Compile a bounded FFmpeg plan without executing or writing anything."""
        return compile_project(read_json(safe_path(root,project_path)),root)
    @server.tool(structured_output=True)
    def propose_edit(project_path: str, expected_revision: str, section: str, clip_id: str, field: str, value_json: str) -> dict[str, Any]:
        """Return a new validated project and reversible edit; no write, render or side effects."""
        need(len(value_json)<=100,'Edit value too large')
        project=read_json(safe_path(root,project_path));validate(project,root)
        return edit(project,expected_revision,section,clip_id,field,json.loads(value_json))
    @server.tool(structured_output=True)
    def audio_qc(audio_path: str) -> dict[str, Any]:
        """Measure 16bit PCM WAV peak/RMS/DC; not LUFS, voice quality or true peak."""
        return inspect_wav(safe_path(root,audio_path))
    if allow_render:
        @server.tool(structured_output=True)
        def render_preview(project_path: str, expected_revision: str) -> dict[str, Any]:
            """Explicitly render local CPU preview. New immutable folder; may take time. No GPU or paid calls."""
            project=read_json(safe_path(root,project_path));need(digest(project)==expected_revision,'Stale revision')
            relative='renders/av-'+uuid.uuid4().hex
            out=safe_path(root,relative,False)
            receipt=render(project,root,out)
            return {'output_directory':relative,'receipt':receipt}
    return server

def build_server(workspace, allow_render=False):
    """Compatibility entry point for the existing offline workspace adapter."""
    return build_workspace_server(workspace,allow_render)

def _json_object(value, label):
    need(isinstance(value,str) and len(value)<=1024*1024,label+' is too large')
    try:result=json.loads(value)
    except json.JSONDecodeError as exc:raise ValueError(label+' must be JSON') from exc
    need(isinstance(result,dict),label+' must be a JSON object');return result

def build_studio_server(studio, allow_edit=False, allow_render=False):
    """API-only adapter. It never reads Studio DBs/files or runs a second worker."""
    from mcp.server import MCPServer
    client=StudioClient(studio)
    server=MCPServer('Local Asset Studio Scene API',instructions='This adapter only calls the running loopback Studio API. Reads are safe by default. Proposals use the server preview action; edits and rendering require explicit startup flags.')
    @server.tool(structured_output=True)
    def capabilities() -> dict[str, Any]:
        """Return server capabilities and this adapter's enabled mutation permissions."""
        result=client.list();return {'studio':result.get('capabilities',{}),'allow_edit':allow_edit,'allow_render':allow_render,'operations':['list_scenes','inspect_scene','workspace_sources','propose_edit']+(['create_scene','edit_scene','restore_scene','export_scene'] if allow_edit else [])+(['render_scene','cancel_render'] if allow_render else [])}
    @server.tool(structured_output=True)
    def list_scenes() -> dict[str, Any]:
        """List persisted Scene editor projects without rendering or changing them."""
        return client.list()
    @server.tool(structured_output=True)
    def inspect_scene(scene_id: str) -> dict[str, Any]:
        """Read one persisted scene, revision, source provenance and render state."""
        return client.inspect(scene_id)
    @server.tool(structured_output=True)
    def workspace_sources() -> dict[str, Any]:
        """List registered Workspace assets that may be selected when creating a scene."""
        return client.workspace()
    @server.tool(structured_output=True)
    def propose_edit(scene_id: str, expected_revision: int, section: str, clip_id: str, changes_json: str) -> dict[str, Any]:
        """Validate an edit with the API preview action; the scene remains unchanged."""
        return client.command(scene_id,{'action':'preview','expected_revision':expected_revision,'section':section,'clip_id':clip_id,'changes':_json_object(changes_json,'Changes')},'agent')
    if allow_edit:
        @server.tool(structured_output=True)
        def create_scene(request_json: str) -> dict[str, Any]:
            """Create a scene from existing registered Workspace asset IDs only."""
            return client.create(_json_object(request_json,'Create request'),'agent')
        @server.tool(structured_output=True)
        def edit_scene(scene_id: str, request_json: str) -> dict[str, Any]:
            """Apply one non-render scene command with its exact expected revision."""
            request=_json_object(request_json,'Scene command');need(request.get('action') in ('edit','move','split','add','remove'),'Unsupported editable scene action')
            return client.command(scene_id,request,'agent')
        @server.tool(structured_output=True)
        def restore_scene(scene_id: str, expected_revision: int, source_revision: int) -> dict[str, Any]:
            """Restore a historical revision as a new persisted scene revision."""
            return client.command(scene_id,{'action':'restore','expected_revision':expected_revision,'source_revision':source_revision},'agent')
        @server.tool(structured_output=True)
        def export_scene(scene_id: str, expected_revision: int) -> dict[str, Any]:
            """Create or return the companion source ZIP for this exact revision."""
            return client.command(scene_id,{'action':'export','expected_revision':expected_revision},'agent')
    if allow_render:
        @server.tool(structured_output=True)
        def render_scene(scene_id: str, expected_revision: int) -> dict[str, Any]:
            """Explicitly queue one immutable render attempt through Studio's owned worker."""
            return client.command(scene_id,{'action':'render','expected_revision':expected_revision},'agent')
        @server.tool(structured_output=True)
        def cancel_render(scene_id: str, render_id: str) -> dict[str, Any]:
            """Request cancellation only for the named active Studio render attempt."""
            return client.command(scene_id,{'action':'cancel','render_id':render_id},'agent')
    return server

def main():
    parser=argparse.ArgumentParser(description=__doc__);target=parser.add_mutually_exclusive_group(required=True);target.add_argument('--workspace');target.add_argument('--studio',help='loopback Studio API origin')
    parser.add_argument('--allow-edit',action='store_true',help='expose persisted scene edits through the Studio API');parser.add_argument('--allow-render',action='store_true',help='expose explicit Studio render/cancel commands');args=parser.parse_args()
    if args.workspace and args.allow_edit:parser.error('--allow-edit requires --studio')
    server=build_workspace_server(args.workspace,args.allow_render) if args.workspace else build_studio_server(args.studio,args.allow_edit,args.allow_render)
    server.run(transport='stdio')
if __name__=='__main__':main()
