/* Entry for app/static/ui-dist/island.js. Loaded by studio-shell.js only behind ?ui=island. The island owns one new
   root after the legacy guidance aside; no legacy node is moved, cloned or rewritten. */
import './island.css';
import { createBrowserHost } from './host';
import { mountIsland, type IslandHandle } from './island';

type IslandWindow = Window & { StudioUiIsland?: unknown };

function start(win: IslandWindow): void {
  const doc = win.document, create = doc.getElementById('createView');
  if (!create || doc.getElementById('uiIsland')) return;
  const root = doc.createElement('section');
  root.id = 'uiIsland';
  root.className = 'ui-island';
  root.setAttribute('aria-labelledby', 'uiIslandTitle');
  const legacy = doc.getElementById('workshopGuidance');
  if (legacy?.parentElement === create) legacy.after(root); else create.append(root);
  const host = createBrowserHost(win);
  let handle: IslandHandle = mountIsland(root, host);
  win.StudioUiIsland = Object.freeze({
    state: () => handle.state(),
    unmount: () => handle.unmount(),
    remount: () => { handle.unmount(); handle = mountIsland(root, host); return handle.state(); }
  });
}

start(window);
