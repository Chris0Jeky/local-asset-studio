"""Original _verify_bundle pixel predicate, extracted from #368 for comparison.

Mode/size and raw bytes AND converted RGBA bytes must match. ICC is a separate
caller check. No extra cleanup is added to this measured baseline.
"""

def same_pixels(a, b):
    return (a.mode == b.mode and a.size == b.size
            and a.tobytes() == b.tobytes()
            and a.convert('RGBA').tobytes() == b.convert('RGBA').tobytes())
