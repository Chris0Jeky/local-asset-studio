# Scavenge queue

## Done
- Batch 1 — catalog + quality ranking + 2.1 appendix → PR #756 / issues #757–#764
- Batch 2 — done → report to Grok for PR #756 (BATCH2.md)

## In flight — Batch 3 (Chris 2026-09-21): tags / prompts / wildcards / workflows
**Status:** started after batch 2 report to Grok.

### Scope (no weight downloads)
1. **Anime / illustration (SFW-default lane)**  
   - Danbooru-style tag guides for WAI Illustrious / Animagine / NoobAI  
   - Quality tags, artist tags, character vs general tag order  
   - Effective negative prompts per base  
   - Wildcard packs (SFW) that work with Dynamic Prompts / Comfy wildcards  
   - Proven workflows: character sheet, multi-angle, outfit change (non-explicit)

2. **Fantasy (SFW-leaning)**  
   - Style stacks (Velvet Mythic etc. already noted — deepen prompt recipes)  
   - Creature / armor / magic FX tag patterns  
   - Lighting / atmosphere wildcards

3. **Hentai / explicit (EXPLICIT QUEUE ONLY)**  
   - Separate section + files (`BATCH3_EXPLICIT.md`) — never mixed into SFW defaults  
   - Tag taxonomies, rating tags (WAI safety: general/sensitive/nsfw/explicit)  
   - Prompt patterns / wildcards / workflows that are popular *and* base-matched  
   - Flag nsfwLevel; quarantine Noob month character-NSFW for hobby-only  
   - civitai.red OK as mirror; still no weight downloads

4. **Cross-cutting**  
   - Sampler/CFG reminders per base (no Pony score_9 on Illu)  
   - Wildcard file formats LAS/Comfy can ingest  
   - Articles with high bookmarks (civitai articles API)

### Deliverables
- `BATCH3.md` (SFW anime + fantasy)
- `BATCH3_EXPLICIT.md` (hentai — explicit queue)
- Append to FINDINGS / LINKS / SOURCES / COMPRESSED
- Update PR #756 only (no new issue set unless Chris asks)
- Mirror desktop pack

### Constraints
- Quality/thumbs over downloads
- Match LoRAs/wildcards to installed bases (WAI v170, NoobAI, Pony, Animagine, RealVis)
- 16GB AMD notes when workflows mention CUDA-only nodes
