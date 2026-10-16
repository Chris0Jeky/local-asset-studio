from pathlib import Path
import json, html, hashlib
R=Path(__file__).resolve().parent
T=json.loads((R/'tokens.json').read_text())
css=['/* Staged source specimen. Not imported by the application. */','.las-kit{']
css += [f'  --{k}:{v};' for k,v in T['base'].items()]
css += [f'  --font-size-{n}:{n}px;' for n in T['type_px']]
css += [f'  --space-{n}:{n}px;' for n in T['spacing_px']]
css += ['  --weight-normal:400;--weight-strong:600;--leading-tight:1.3;--leading-body:1.5;--radius-pill:999px;', '  --elevation-0:none;--elevation-1:0 2px 5px #0003;--elevation-2:0 6px 18px #0005;--elevation-3:0 16px 40px #0007;--elevation-dock:0 -6px 24px #0008;', '  --sidebar-expanded:224px;--sidebar-collapsed:64px;--topbar-height:60px;--dock-height:72px;--row-height:44px;', '  --font-ui:"Segoe UI Variable","Segoe UI",system-ui,sans-serif;','  --font-mono:"Cascadia Code",Consolas,monospace;','  --motion-fast:140ms;--motion-panel:180ms;--motion-scene:240ms;','  --control-height:40px;--gap:16px;--radius-input:4px;--radius-card:8px;--radius-dialog:12px;', '}']
for name,skin in T['skins'].items():css.append('.las-kit[data-skin="'+name+'"]{'+''.join('--'+k+':'+v+';' for k,v in skin.items())+'}')
css.append('''
.las-kit{font:14px/1.5 var(--font-ui);color:var(--text);background:var(--bg);padding:24px;border-radius:12px;color-scheme:dark}
.las-kit *{box-sizing:border-box}.las-kit [hidden]{display:none!important}
.las-kit[data-density="compact"]{--control-height:32px;--gap:8px;--row-height:36px}
.las-kit h1,.las-kit h2,.las-kit h3{line-height:1.3;font-weight:600}.las-kit h1{font-size:32px}.las-kit h2{font-size:24px}.las-kit h3{font-size:20px}
.las-kit p{max-width:76ch}.las-kit .muted{color:var(--text-muted)}.las-kit .faint{color:var(--text-faint)}
.las-kit .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:var(--gap)}
.las-kit .card{padding:16px;border:1px solid var(--line);border-radius:var(--radius-card);background:var(--surface-1);min-width:0;box-shadow:0 2px 5px #0003}
.las-kit .toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.las-kit .stack>*+*{margin-top:12px}
.las-kit button,.las-kit input,.las-kit textarea,.las-kit select{font:inherit;max-width:100%;min-height:var(--control-height);border:1px solid var(--line-strong);border-radius:var(--radius-input)}
.las-kit button{padding:7px 12px;min-width:32px;background:var(--surface-2);color:var(--text);cursor:pointer}
.las-kit button.primary{background:var(--accent);color:var(--text-on-accent);border-color:var(--accent);font-weight:600}
.las-kit button.primary:hover:not(:disabled){background:var(--accent-hover)}
.las-kit button.ghost{background:transparent}.las-kit button.danger{background:var(--status-error);border-color:var(--status-error);color:var(--text-on-accent)}
.las-kit button:disabled{color:var(--text-muted);background:var(--surface-2);cursor:not-allowed;border-style:dashed;opacity:1}
.las-kit :is(button,input,textarea,select,a,summary):focus-visible{outline:2px solid var(--focus-ring);outline-offset:3px;box-shadow:0 0 0 2px var(--focus-underlay)}
.las-kit input,.las-kit textarea,.las-kit select{display:block;width:100%;padding:8px;background:var(--surface-2);color:var(--text)}
.las-kit textarea{min-height:100px;resize:vertical}.las-kit label{display:block;font-weight:600;margin-bottom:4px}
.las-kit .reason{margin:6px 0 0;color:var(--text-muted)}.las-kit a{color:var(--accent);text-underline-offset:3px}
.las-kit .tabs{display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:8px}
.las-kit .tabs .selected{border-bottom:3px solid var(--accent);font-weight:600}
.las-kit .chip{display:inline-flex;gap:7px;align-items:center;border:1px solid currentColor;border-radius:999px;padding:3px 9px;white-space:normal}
.las-kit .state-mark{width:10px;height:10px;border:2px solid currentColor;flex:none}.las-kit .is-running .state-mark{border-radius:50%}.las-kit .is-unknown .state-mark{transform:rotate(45deg)}.las-kit .is-failed .state-mark{border-style:double}
.las-kit .is-running{color:var(--status-running)}.las-kit .is-success{color:var(--status-success)}.las-kit .is-warning{color:var(--status-warning)}.las-kit .is-failed{color:var(--status-error)}.las-kit .is-unknown{color:var(--status-unknown)}.las-kit .is-neutral{color:var(--status-neutral)}.las-kit .is-muted{color:var(--status-muted)}
.las-kit .keeper{color:var(--review-keeper)}.las-kit .needs-work{color:var(--review-needs-work)}.las-kit .rejected{color:var(--review-rejected)}.las-kit .unreviewed{color:var(--review-unreviewed)}
.las-kit .notice{padding:12px;border:1px solid currentColor;border-left-width:4px;border-radius:4px;background:var(--surface-1)}
.las-kit details{border-top:1px solid var(--line);padding-top:8px}.las-kit summary{cursor:pointer;min-height:32px;padding:5px}
.las-kit kbd{font:12px var(--font-mono);border:1px solid var(--line-strong);border-bottom-width:2px;border-radius:4px;padding:2px 5px}
.las-kit .dialog-specimen{max-width:540px;padding:24px;background:var(--surface-3);border:1px solid var(--line-strong);border-radius:var(--radius-dialog);box-shadow:0 16px 40px #0007}
.las-kit .empty{padding:24px;border:1px dashed var(--line-strong);text-align:center}
.las-kit .pattern{background-image:radial-gradient(var(--line) 1px,transparent 1px);background-size:16px 16px;height:80px;border-radius:8px}
.las-kit .skeleton>span{display:block;background:var(--surface-3);height:12px;margin:8px 0;border-radius:4px}.las-kit .skeleton>span:last-child{width:65%}
.las-kit .swatch{display:inline-block;width:24px;height:24px;border:1px solid var(--line-strong);vertical-align:middle;margin-right:8px}
.las-kit .ui-feedback{transition:background-color var(--motion-fast) ease-out,color var(--motion-fast) ease-out}
.las-kit .panel-enter{transition:opacity var(--motion-panel) ease-out}.las-kit .scene-layer{transition:opacity var(--motion-scene) ease-out}
.las-kit[data-motion="paused"] .decorative{animation-play-state:paused!important}.las-kit[data-motion="static"] :is(.decorative,.ui-feedback,.panel-enter,.scene-layer){animation:none!important;transition:none!important}
@media(max-width:430px){.las-kit{padding:12px}.las-kit h1{font-size:24px}.las-kit .dialog-specimen{padding:16px}.las-kit .toolbar>*{max-width:100%}}
@media(prefers-reduced-motion:reduce){.las-kit{--motion-fast:0ms;--motion-panel:0ms;--motion-scene:0ms}.las-kit *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
@media(forced-colors:active){.las-kit *{animation:none!important;transition:none!important}.las-kit{color:CanvasText;background:Canvas}.las-kit .decorative{display:none}.las-kit :is(.card,.chip,.notice,.dialog-specimen){color:CanvasText;background:Canvas;border-color:CanvasText}.las-kit button{color:ButtonText;background:ButtonFace;border-color:ButtonText}.las-kit :is(input,textarea,select){color:FieldText;background:Field;border-color:FieldText}.las-kit :focus-visible{outline-color:Highlight;box-shadow:none}.las-kit .state-mark{border-color:CanvasText}.las-kit .pattern{background:none}}
''')
(R/'foundations.css').write_text('\n'.join(css))
states=[('Queued','neutral'),('Waiting','neutral'),('Submitting','running'),('Running','running'),('Completed','success'),('Partial','warning'),('Failed','failed'),('Uncertain outcome','unknown'),('Not submitted','neutral'),('Abandoned','muted'),('Tracking stopped','unknown'),('Put away','muted')]
chips=''.join(f'<span class="chip is-{tone}"><span aria-hidden="true" class="state-mark"></span>{label}</span>' for label,tone in states)
def section(skin):
 return f'''<section class="las-kit" data-skin="{skin}" data-density="comfortable" data-motion="static">
 <h2>{html.escape(skin.replace('-', ' ').title())}</h2><p class="muted">Source design specimen. Controls do not run, install, switch engines, save drafts or change your Studio.</p>
 <div class="grid"><article class="card stack"><h3>Buttons and reasons</h3><div class="toolbar"><button class="primary" type="button">Primary</button><button type="button">Secondary</button><button class="ghost" type="button">Ghost</button><button class="danger" type="button">Danger</button></div><button type="button" disabled aria-describedby="reason-{skin}">Generate</button><p class="reason" id="reason-{skin}">Example reason: a source image is required. This sheet submits no jobs.</p><a href="#fields-{skin}">Inspect the field specimen</a></article>
 <article class="card stack" id="fields-{skin}"><h3>Fields</h3><label for="brief-{skin}">Brief</label><textarea id="brief-{skin}">Public sample: an original quiet workshop</textarea><label for="name-{skin}">Name</label><input id="name-{skin}" value="Untitled study"><label for="recipe-{skin}">Recipe specimen</label><select id="recipe-{skin}"><option>Example recipe only</option></select></article>
 <article class="card stack"><h3>Navigation and cards</h3><nav class="tabs" aria-label="Tab-style specimen"><button type="button" class="selected">Overview</button><button type="button">Details</button></nav><p class="muted">Tab appearance only. No tab-role keyboard behaviour is claimed.</p><details><summary>Why?</summary><p>Details are behind native disclosure. Opening it never starts a job.</p></details><p><kbd>Ctrl</kbd> + <kbd>Enter</kbd> is a keyboard-hint specimen only.</p></article>
 <article class="card stack"><h3>Execution state</h3><div class="toolbar">{chips}</div><p class="muted">Uncertain outcome retains the receipt. Offer Check again after real integration, never Retry.</p></article>
 <article class="card stack"><h3>Review is separate</h3><div class="toolbar"><span class="chip keeper">Keeper</span><span class="chip needs-work">Needs work</span><span class="chip rejected">Rejected</span><span class="chip unreviewed">Unreviewed</span></div><p>Completed execution does not mean accepted artwork or licensed output.</p><div class="notice is-warning">Example notice: source terms have not been reviewed.</div></article>
 <article class="card stack"><h3>Empty and placeholder patterns</h3><div class="empty"><p>No results in this specimen</p><button type="button">Example action</button></div><div class="pattern decorative" aria-hidden="true"></div><div class="skeleton" aria-hidden="true"><span></span><span></span><span></span></div><p class="muted">Static placeholders, not progress feedback.</p></article></div>
 <h3>Dialog visual specimen</h3><section class="dialog-specimen" aria-label="Dialog styling specimen"><h3>Review this change</h3><p>This is a static section, not an implemented modal. Production needs native dialog semantics, focus containment, Escape and focus restoration.</p><div class="toolbar"><button type="button">Cancel appearance</button><button class="primary" type="button">Confirm appearance</button></div></section></section>'''
doc='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LAS foundation source specimens</title><link rel="stylesheet" href="foundations.css"><style>body{margin:0;padding:16px;background:#101216;color:#f3efe7;font:14px system-ui,sans-serif}.las-kit{margin:20px auto;max-width:1440px}header{max-width:1440px;margin:auto}a{color:inherit}</style></head><body><header><h1>Local Asset Studio · foundation source specimens</h1><p>Six token skins, fixed execution/review semantics, native field examples and static component appearances. No runtime integration or accessibility certification. All content is public synthetic example text.</p></header>'+''.join(section(s) for s in T['skins'])+'</body></html>'
(R/'components.html').write_text(doc)
cover='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630"><rect width="1200" height="630" fill="#131416"/><rect x="760" y="126" width="286" height="350" rx="12" fill="#25262b" stroke="#ffb18b" stroke-width="3"/><path d="M796 180h200M796 220h140M796 374h200" fill="none" stroke="#b6b2ac" stroke-width="3"/><rect x="690" y="346" width="248" height="144" rx="8" fill="#1c1d21" stroke="#92969e" stroke-width="3"/><text x="80" y="258" fill="#f3efe7" font-family="system-ui,sans-serif" font-size="62">Local Asset Studio</text><text x="84" y="318" fill="#c0bcb6" font-family="system-ui,sans-serif" font-size="26">Local creative workspace</text><text x="84" y="452" fill="#ffb18b" font-family="system-ui,sans-serif" font-size="20">Source design study · editable assets</text></svg>'''
(R/'promo-readme.svg').write_text(cover)
print(json.dumps({'skins':len(T['skins']),'status_chips_per_skin':len(states),'css_bytes':(R/'foundations.css').stat().st_size,'html_bytes':(R/'components.html').stat().st_size}))
