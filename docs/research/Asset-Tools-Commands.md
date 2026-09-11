> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

# Local asset tools

Run these in PowerShell. The tools refuse to overwrite existing image outputs. Use a new output name for each revision.

```powershell
$python = 'C:\AI\asset-tools\venv\Scripts\python.exe'
$assets = 'C:\AI\asset-tools\assets.py'
```

## Slice a regular sprite sheet

```powershell
& $python $assets slice .\sheet.png .\frames --size 32 32
```

The sheet must be an unpadded grid whose dimensions divide evenly by the cell size. It crops pixels exactly; it does not invent animation frames. The first filename number is the row, the second is the column. Irregular layouts need explicit rectangles or manual cleanup in Pixelorama.

## Pack frames into an atlas

```powershell
$frames = Get-ChildItem .\frames\*.png | Sort-Object Name | ForEach-Object FullName
& $python $assets atlas .\atlas.png @frames --columns 4 --padding 2
```

The JSON alongside the PNG records each frame rectangle and a normalized center pivot. Keep the original canvases aligned for consistent pivots. These are generic frame records, not an engine-specific import format. Padding is transparent; edge extrusion and engine metadata can be added for a specific project.

## Make an animation preview

```powershell
& $python $assets gif .\preview.gif @frames --ms 150
```

The GIF uses a dark preview background. Keep PNGs as the transparent production masters. All frames must have matching canvas sizes.

## Preserve pixels outside a change

```powershell
& $python $assets composite .\original.png .\edited.png .\mask.png .\result.png
```

All three inputs must have identical dimensions. White mask pixels take the edit, black pixels keep the original exactly, and gray pixels blend. This is the final step after generative editing when exact preservation matters. Use PNG for lossless output. A feathered mask intentionally changes the feathered region.

## Remove a background locally

```powershell
& $python $assets remove-bg .\input.png .\cutout.png
```

Uses the downloaded U2NetP model on the CPU. This is a lightweight baseline: inspect hair, glass, holes, and fine outlines in Krita. Blender can render an alpha channel directly, which is preferable for 3D assets.

## Export for a website

```powershell
& $python $assets web .\master.png .\hero.webp --width 1200
```

This preserves aspect ratio and avoids enlarging small inputs. It does not automatically find the subject or choose art direction for responsive crops.

## Blender through Codex

The tested executable is `C:\AI\blender-4.5.13-windows-x64\blender.exe`. Codex can write a Python script using `bpy`, run Blender in the background, inspect the rendered PNGs, and revise the scene. The saved example is `asset-demo/lantern.blend` alongside this guide. Its generator is `C:\AI\asset-tools\blender-demo.py`.

```powershell
& 'C:\AI\blender-4.5.13-windows-x64\blender.exe' -b .\scene.blend -o .\renders\frame_ -F PNG -f 1
```

For new work, useful requests are: “make eight directional renders of this prop”, “render three product lighting setups”, or “create a rigged placeholder and export a walk-cycle sheet”. A Blender connector is not necessary for this tested command-line route.

## Repeatable generation

ComfyUI's local API accepts saved API-format graphs at `POST /prompt`; results are available through `/history/<prompt_id>`. The visible editor workflow JSON and API graph JSON are different formats. Use ComfyUI's API export for automation. Keep seeds, model hashes, prompts, workflow versions, and selected output names with each asset pack.

The recommended first batch is a small matching set of props or icons with one style reference. Review a contact sheet, then finish and export only the selected candidates. Further automation can add engine-specific metadata, export dimensions, palette checks, and asset manifests once a real project provides those requirements.
