# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
import ns, json, sys
meta = json.load(open(ns.HERE + 'anchor-upload.json'))
A = ("Change one thing: make it a quiet early morning instead of night. Soft cool daylight comes through the window, the rain has stopped "
     "and the sky outside is pale blue-grey over a calm morning city, the train is gone, the monitor screen is dark and switched off, "
     "and the warm desk lamp is still on. Keep everything else exactly as it is: the camera angle and framing, the room, the plain "
     "graphite wall on the left, the window frame, the desk, the chair, the lamp and the monitor in the same places, the floor, and the "
     "hand-painted cel anime film background style.")
B = ("Change the time of day from rainy night to calm early morning: cool pale daylight from the window gently lights the room, the "
     "city outside is misty and quiet, no rain, the desk lamp glows warm, the monitor screen is off. Keep the same camera, the same room "
     "layout, every object in the same position, the same plain wall on the left, and the same hand-painted cel anime background style.")
WORDS = {'A': A, 'B': B}
def run(key, words, seed, extra=None):
    c = {'reference': meta['file'], 'positive': words, 'seed': seed, 'width': 1344, 'height': 768}; c.update(extra or {})
    return ns.studio_job(key, 'flux-edit', c, ns.ANCHOR_SHA, label='nightshift-' + key)
if __name__ == '__main__':
    for key, w, seed in [('quiet-a1', 'A', 2026092781), ('quiet-a2', 'A', 2026092782), ('quiet-b1', 'B', 2026092781), ('quiet-b2', 'B', 2026092782)]:
        run(key, WORDS[w], seed)
