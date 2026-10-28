// Fictional observations, shaped like the existing Workspace readers. No media bytes or runtime probes.
export const workspaceId = 'a'.repeat(32);
export const catalogue = {epoch: 'b'.repeat(32), revision: 1};
const asset = (id, title, media_type, filename, n) => ({
  id, title, media_type, filename, sha256: n.toString(16).repeat(64), bytes: 1,
  metadata_revision: 0, review: 'unreviewed', favorite: false, created_at: 1800000000 - n,
  trashed_at: null, preset_id: null, preset_name: null, url: `/api/assets/${id}/file`, truncated_fields: []
});
export const assets = [
  asset('marsh-dusk', 'Marsh at dusk', 'image', 'marsh-dusk.png', 1),
  asset('marsh-moon', 'Moonlit crossing', 'image', 'marsh-moon.png', 2),
  asset('keeper', 'Lantern keeper silhouette', 'image', 'keeper.png', 3),
  asset('brass-key', 'Brass key concept', 'image', 'brass-key.png', 4),
  asset('reeds', 'Reeds in the wind', 'video', 'reeds.mp4', 5),
  asset('marsh-bed', 'Marsh ambience', 'audio', 'marsh-bed.wav', 6),
  asset('keeper-line', 'Keeper greeting', 'audio', 'keeper-line.wav', 7),
  asset('lantern-mesh', 'Lantern blockout', '3d', 'lantern.glb', 8)
];
export const collectionPage = {
  format: 'studio.collection-page/v1', workspace_id: workspaceId, catalogue, limit: 25,
  order: 'name_nocase_asc_id_asc', collections: [{id: 'lantern-marsh', name: 'Lantern Marsh',
    description: 'Fictional small game scene', revision: 1, count: assets.length}], next_cursor: null,
  observation_only: true, media_bytes_verified: false, generation_submitted: false
};
export const assetPage = {
  format: 'studio.asset-page/v1', workspace_id: workspaceId, catalogue, limit: 25,
  filters: {visibility: 'active', media_type: null, review: null, favorite: null, collection_id: 'lantern-marsh'},
  order: 'created_at_desc_id_desc', assets, next_cursor: null,
  observation_only: true, media_bytes_verified: false, generation_submitted: false
};
export const previews = {
  'marsh-dusk': {drawing: 'marsh', detail: 'PNG · 1280 × 720 · painted scene study'},
  'marsh-moon': {drawing: 'moon', detail: 'PNG · 1280 × 720 · alternate composition'},
  keeper: {drawing: 'sprite', detail: 'PNG · 256 × 256 · single pose, no sheet'},
  'brass-key': {drawing: 'key', detail: 'PNG · 128 × 128 · edge cleanup unverified'},
  reeds: {drawing: 'video', detail: 'MP4 · 4 seconds · loop seam unverified'},
  'marsh-bed': {drawing: 'audio', detail: 'WAV · 48 kHz PCM · 12 seconds'},
  'keeper-line': {drawing: 'audio', detail: 'WAV · 48 kHz PCM · 3 seconds'},
  'lantern-mesh': {drawing: '3d', detail: 'GLB · static blockout · scale and topology unverified'}
};
export const slots = [
  {id: 'background', name: 'Background', kind: 'image', drawing: 'marsh',
    intent: 'A quiet marsh crossing at blue hour. One warm lantern leads the player toward the bridge.',
    criteria: '1280 × 720 PNG; leave the lower third clear for the player; check foreground separation.',
    initial: 'marsh-dusk', routes: ['image'], gap: 'Check composition, game fit and rights.'},
  {id: 'sprite', name: 'Keeper sprite', kind: 'image', drawing: 'sprite',
    intent: 'A small lantern keeper with a readable silhouette, coat and warm brass lantern.',
    criteria: 'Four directional idle frames, 64 × 64 each; transparent background; consistent silhouette.',
    routes: ['sprite'], gap: 'A single pose is not a directional sheet. Author and inspect the frames.'},
  {id: 'icon', name: 'Brass key icon', kind: 'image', drawing: 'key',
    intent: 'An old brass key with a leaf-shaped bow, readable against the dark inventory.',
    criteria: '128 × 128 PNG; transparent background; inspect edges and readability at 32 px.',
    routes: ['icon'], gap: 'Check transparency, small-size readability and rights.'},
  {id: 'loop', name: 'Atmosphere loop', kind: 'video', drawing: 'video',
    intent: 'Four seconds of quiet reeds and lantern light. Motion must feel calm behind dialogue.',
    criteria: '640 × 360 MP4, 24 fps, 4 seconds; inspect the loop seam and avoid abrupt motion.',
    routes: ['scene', 'h3'], gap: 'Scene composition does not prove a seamless loop. Inspect the join.'},
  {id: 'sound', name: 'Sound / voice', kind: 'audio', drawing: 'audio',
    intent: 'Mind the bridge. The marsh keeps what falls.',
    criteria: '48 kHz PCM WAV; quiet ambience or an original keeper line; check levels, performance and rights.',
    initial: 'marsh-bed', routes: ['voice'], gap: 'Listen for levels and performance; confirm rights.'},
  {id: 'model', name: '3D lantern draft', kind: '3d', drawing: '3d',
    intent: 'A compact brass lantern with a broad handle and one protected flame.',
    criteria: 'GLB draft; inspect scale, topology, materials and game-engine import. No rig promised.',
    routes: ['trellis', 'hunyuan'], gap: 'Inspect topology, scale, materials, import and rights.'}
];
export const routes = {
  image: {name: 'Prepare a background', owner: 'Make · saved look', state: 'preview',
    endpoint: '/api/looks/prepare', lookId: 'look-night-shift-retro-anime',
    description: 'Compose the scene wording into an existing look. Preparation and generation are separate.',
    prerequisites: ['Look revision: fixture 1', 'Runtime and model readiness: not checked'], result: 'image'},
  icon: {name: 'Prepare an icon concept', owner: 'Make · game item', state: 'preview',
    endpoint: '/api/looks/prepare', lookId: 'look-zimage-game-icon',
    description: 'An image concept route. Transparency and a usable game icon still need inspection.',
    prerequisites: ['Look revision: fixture 1', 'Runtime and model readiness: not checked'], result: 'image'},
  sprite: {name: 'Directional sprite sheet', owner: 'External authoring', state: 'unsupported',
    description: 'The current pixel-art presets make images. They do not promise four consistent directional frames.',
    prerequisites: ['Author frames in a sprite editor', 'Import the resulting sheet through the Library']},
  scene: {name: 'Compose a scene', owner: 'Scene editor · existing assets', state: 'preview', endpoint: '/api/av',
    description: 'Arrange the selected background and sound in a 96-frame scene. This does not animate the painting or prove a loop.',
    prerequisites: ['Selected PNG background', 'Optional 48 kHz PCM WAV', 'FFmpeg, source bytes and space: not checked'], result: 'video'},
  h3: {name: 'Generate a moving clip', owner: 'MiniMax H3 · preview', state: 'blocked', presetId: 'h3-preview',
    description: 'A catalogued video route, but this preview has no observed backend or model readiness.',
    prerequisites: ['Isolated H3 environment must be available', 'Check model files, resource admission and clip length']},
  voice: {name: 'Prepare a voice take', owner: 'Voice takes · Kokoro baseline', state: 'blocked', endpoint: '/api/voice-baseline',
    description: 'Uses the existing original-line voice planner. The fixture reports its pinned voice bundle unavailable.',
    prerequisites: ['Pinned Kokoro bundle: missing in fixture', 'FFmpeg and version checks: not performed']},
  trellis: {name: 'Prepare a 3D draft', owner: 'TRELLIS.2 · transparent reference', state: 'blocked', presetId: 'trellis-rgba',
    description: 'The catalogue accepts a transparent reference. No suitable reference has been attached and runtime readiness is unknown.',
    prerequisites: ['Attach and validate an RGBA source', 'Observe environment, model and memory readiness']},
  hunyuan: {name: 'Hunyuan3D 2.1', owner: 'Catalogue restriction', state: 'unsupported', presetId: 'hunyuan-draft',
    description: 'The repository records a UK exclusion for this route. It is unavailable in this UK scenario.',
    prerequisites: ['Choose an eligible route or reuse an existing draft; rights remain a separate check']}
};
export function resultAsset(slotId) {
  const slot = slots.find(s => s.id === slotId);
  if (!slot || !['background', 'icon', 'loop'].includes(slotId)) return null;
  return asset(`synthetic-${slotId}`, `${slot.name} · returned candidate`, slot.kind,
    `synthetic-${slotId}.${slot.kind === 'video' ? 'mp4' : 'png'}`, 9);
}
export function findAsset(id) { return assets.find(a => a.id === id) || slots.map(s => resultAsset(s.id)).find(a => a?.id === id); }
