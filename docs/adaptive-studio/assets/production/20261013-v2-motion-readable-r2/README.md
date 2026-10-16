# Readable optional motion — R2

The owner reported LAS looked entirely still and Alibi barely moved. R1 timing tests passed but perceptual delivery failed. R1 files, delivered clips and their hashes remain preserved. This R2 sibling changes only preview motion; the provisionally accepted v2 static SVG is byte-identical.

Open `index.html`, then press Play. The LAS demo now has train passage enabled, with visible native falling drops inside the unchanged window clip. Train movement is always one-way when visible; its discrete reset happens fully outside the window, behind stationary joinery. Alibi uses anchored rigid flame rotation, gradual local light variation and two rising/dissipating steam plumes. Counters and furniture stay stationary. Preview-only vector overlays are editable in the external controller/CSS; no raster is embedded in SVG and no dependency is added.

Complete default still, explicit Play/Pause, reduced-motion still and hidden/offscreen pausing are retained. The shared loop is8 seconds; illustrative exports use24 fps and explicitly record enabled effects. Exported videos are previews, not editable source.

Run `python verify_preview.py --evidence <folder>` for lifecycle/initial-pixel/seam checks and `python assert_readable_export.py las|alibi <video> --output <folder>` for decoded-card-region checks. Decoded motion and measured displacement reject an all-still or near-still export; they do not establish human visual acceptance. Complete normal-speed playback is reviewed separately. Hidden-document evidence remains a DOM-contract probe rather than physical-device qualification.

No runtime, catalogue, precache, budget, dependency, merge or deployment change. Limited provisional acceptance applies the previously displayed v2 workshop/lantern and responsive LAS card; failed coarse studies and new motion acceptance are not included.
