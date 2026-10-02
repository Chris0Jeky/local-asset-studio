# Motion source contracts

These source references cover motion-disclose, motion-crossfade, motion-focus, motion-load and motion-pause. They are not connected to the running Studio and perform no network requests, generation, installation or engine changes.

- Disclose: 180 ms opacity, unchanged hit targets and scroll anchor. Native details remains usable without animation. Production expansion must preserve focus and avoid hiding an active field.
- Crossfade: at most 240 ms, only after the replacement local poster decodes. Hold the old poster until then. Use request epochs and AbortController in the integration; a stale skin response must never replace the current selection. No overlap budget or actual compositor result is claimed by this source kit.
- Focus: immediate visible dual ring. The inner dark underlay separates focus from a bright accent button; the outer light ring separates it from dark panels. Do not animate focus into visibility.
- Load: reserve geometry, use a static placeholder and concise real HTML state. Do not fabricate percentage or animate a decoration as if it represented job progress. No mandatory spinner or loop.
- Pause: use the pure motionDecision reference to derive permission from current observations. Hidden/out-of-viewport pauses; reduced motion, forced colours, active/unknown jobs and economy choose static. Missing observations fail to static. User pause remains caller-owned and never clears itself. Only explicitly chosen, approved, ready local media while idle and visible may return local-loop. The reference does not invoke play, fetch, timers or application commands.

## Required integration lifecycle

Subscribe to media-query, visibility, viewport and runtime-resource changes through the existing owners. Re-evaluate on each relevant observation, not through polling or third-party reachability probes. Honour rejected play promises. On hide, skin change, unmount or owner change: abort pending optional requests, invalidate request epochs, cancel scheduled frames, remove listeners, and preserve the selected local poster. User pause and Still are independent of internet availability. No autoplay audio.

Reduced motion and forced colours are immediate static alternatives. Parallax, ambient loops and audio production remain in the owner's deferred/evidence-gated scopes; this kit does not create or activate them.

## Verification limits

Node tests exercise the pure decision function and token contrast math. They do not prove DOM cleanup, focus restoration, real playback, GPU resource contention, actual crossfades or browser media-query handling. Those scenarios require a runnable app integration and real browser tests before release selection.
