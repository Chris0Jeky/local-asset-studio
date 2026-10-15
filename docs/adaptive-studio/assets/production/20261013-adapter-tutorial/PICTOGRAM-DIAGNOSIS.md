# Read-only pictogram shell diagnosis

Compared main312dff631fff0a4b964f482442253f2736a83c29 with
icon8b6846a17b0014391a85d48a45c5fea3dea28839. Existing clean builds measured
895 raw shell bytes of growth and a696.68-byte excess; at least697 bytes must be
recovered to fit the unchanged ceiling. Startup remains a separate passing gate.

Read-only source attribution: src/presentation.js grows28935→29884 (+949),
src/app.js grows205581→205587 (+6). Its four changed navigation lines account
for the latter. Minification makes the emitted shell delta smaller than the955
source-byte sum. PICTOGRAM-DELTA.json records every changed fragment's sizes.

No simple representation or deduplication saving of697 bytes is apparent.
tools/build.cjs includes presentation.js once. icon() already shares the SVG
wrapper. Runtime fragments have no exact duplicates. Source master JSON,
generated SVG exports and generator are outside the precached shell: deduplicating
those files would not reduce the measured gate. Existing compaction already
joins adjacent equally styled open contours; the prior read-only extension
analysis found only11 additional bytes available, far short of the requirement.

Most growth is distinct geometry strings. A shared path dictionary or custom
encoder would introduce a representation/decoder change requiring new generator
and runtime validation; no bounded, exact saving that qualifies as simple was
identified. Changing/removing geometry or reverting destination glyphs would
alter the intended icons. Neither is justified by this diagnosis.

An independent read-only reviewer reached the same conclusion. No source edits,
builds, codecs, candidate probes, new dependency or cap relaxation were performed
for this diagnosis. Existing +895 / ~697-over evidence remains the blocker.
