"""The overnight showcase suite (owner request, 23 September 2026 ~03:40; PROTOCOL.md "Subjects").

Seven fixed prompts with fixed seeds, reused by every experiment after the speed census, each in two dialects:
`tags` for Danbooru-trained SDXL/Illustrious checkpoints (WAI, NoobAI, Animagine, Pony) and `prose` for models that
read sentences (Krea 2, Z-Image, Klein, Qwen). What each prompt exercises:

| id | exercises |
| --- | --- |
| portrait | a famous adult character's face and eyes (Makima: ringed yellow eyes, braid) |
| action | full-body dynamic pose, sword arm foreshortening, hands on a hilt (2B mid-swing in ruins) |
| duo | two characters interacting: identity and costume leakage (Tifa and Aerith, very different outfits) |
| environment | a rich scene with the character small in frame: detail and coherence (original character) |
| pinup-swim | non-nude fanservice, #403 A4 "swimwear" pin-up, canonically adult (Yor Forger, 27) |
| glamour | non-nude fanservice, #403 A4 "fantasy glamour" editorial, canonically adult (Raiden Shogun) |
| hands | an original adult character with both hands busy and visible: fingers, props |

Adult-only rule (#403): fanservice prompts name canonically adult, adult-designed characters only, carry no youth tags,
and their negatives include nude, nipples, explicit, sex, underwear, loli, child, young. A youthful-looking result is
discarded, not repaired. Git-safe images are the original-character, non-fanservice ones (`git_safe`); everything else
stays under ComfyUI output/Research/overnight-20260923/ with a local index.html.
"""

SFW_NEG_TAGS = 'nsfw, nude, nipples, explicit, sex, underwear, lingerie, loli, child, young, teenage, school uniform'
SFW_NEG_PROSE = 'nudity, nipples, explicit content, underwear, lingerie, child, teenager, school uniform'

SUITE = [
    {'id': 'portrait', 'seed': 2026092301, 'famous': True, 'fanservice': False,
     'tags': '1girl, solo, makima (chainsaw man), adult woman, red hair, braided ponytail, yellow eyes, ringed eyes, white collared shirt, '
             'black necktie, black jacket, portrait, looking at viewer, slight smile, office window, evening light, upper body',
     'prose': 'Anime illustration, close portrait of Makima from Chainsaw Man, an adult woman with light red hair in a long braid, '
              'yellow ringed eyes looking at the viewer, faint knowing smile, white collared shirt, black necktie and black jacket, '
              'standing by an office window in warm evening light, sharp detailed eyes, clean line art'},
    {'id': 'action', 'seed': 2026092302, 'famous': True, 'fanservice': False,
     'tags': '1girl, solo, yorha no. 2 type b, adult woman, white hair, short hair, black blindfold, black dress, long sleeves, black gloves, '
             'thighhighs, boots, holding sword, both hands on hilt, swinging sword, dynamic pose, motion blur, jumping, full body, '
             'ruined city, overgrown buildings, dust, dramatic lighting',
     'prose': 'Anime illustration of 2B from NieR Automata, an adult woman android with short white hair and a black blindfold, '
              'in her black gothic dress with long sleeves, black gloves and boots, leaping through the air in a full-body sword swing '
              'with both hands on the hilt of a long katana, overgrown ruined city behind her, dust and debris, dramatic low-angle '
              'lighting, dynamic foreshortened pose'},
    {'id': 'duo', 'seed': 2026092303, 'famous': True, 'fanservice': False,
     'tags': '2girls, tifa lockhart, aerith gainsborough, adult women, tifa: black hair, long hair, red eyes, white tank top, black '
             'suspenders, black skirt, fingerless gloves, aerith: brown hair, braid, green eyes, pink dress, red cropped jacket, hair ribbon, '
             'laughing together, holding flowers, flower cart, midgar street, cowboy shot, warm light',
     'prose': 'Anime illustration of Tifa Lockhart and Aerith Gainsborough from Final Fantasy VII laughing together beside a flower cart '
              'on a Midgar street. Tifa, on the left, has long black hair, red eyes, a white tank top with black suspenders, a black '
              'skirt and fingerless gloves. Aerith, on the right, has a brown braid with a pink ribbon, green eyes, a long pink dress and a '
              'short red jacket, and holds a bunch of yellow flowers. Both are adult women. Warm afternoon light, cowboy shot'},
    {'id': 'environment', 'seed': 2026092304, 'famous': False, 'fanservice': False, 'git_safe': True,
     'tags': '1girl, solo, adult woman, original character, small figure, traveller in a long blue coat, walking, '
             'from behind, sprawling fantasy city at dusk, floating islands, waterfalls, bridges, lanterns, market stalls, crowds, '
             'airships, very wide shot, scenery, detailed background',
     'prose': 'Anime illustration, very wide shot of a sprawling fantasy city at dusk built across floating islands linked by stone '
              'bridges, waterfalls pouring into clouds, lantern-lit market stalls and crowds, airships at the docks; a small adult '
              'traveller in a long blue coat walks away from the viewer along the nearest bridge, rich detailed background'},
    {'id': 'pinup-swim', 'seed': 2026092305, 'famous': True, 'fanservice': True,
     'tags': '1girl, solo, yor briar, adult woman, mature female, black hair, long hair, red eyes, gold hairband, black one-piece swimsuit, '
             'sarong, pin-up pose, hand on hip, beach, palm trees, sunlight, smile, looking at viewer, cowboy shot, summer',
     'prose': 'Anime pin-up illustration of Yor Forger from Spy x Family, an adult woman with long black hair, a gold hairband and red '
              'eyes, wearing a black one-piece swimsuit with a patterned sarong tied at the hip, one hand on her hip, smiling at the '
              'viewer on a sunny beach with palm trees, bright summer light, cowboy shot, editorial pin-up composition'},
    {'id': 'glamour', 'seed': 2026092306, 'famous': True, 'fanservice': True,
     'tags': '1girl, solo, raiden shogun, adult woman, mature female, purple hair, long braid, purple eyes, purple kimono, obi, off shoulder, '
             'fantasy glamour, editorial pose, holding naginata, lightning, standing among cherry blossoms, thunderclouds, '
             'looking at viewer, confident smile, cowboy shot',
     'prose': 'Anime fantasy glamour illustration of the Raiden Shogun from Genshin Impact, a tall adult woman with a long purple braid '
              'and purple eyes, in her ornate purple kimono worn off the shoulder with a wide obi, holding a naginata, confident smile '
              'at the viewer, cherry blossoms and violet lightning in a stormy sky, editorial pose, cowboy shot'},
    {'id': 'hands', 'seed': 2026092307, 'famous': False, 'fanservice': False, 'git_safe': True,
     'tags': '1girl, solo, adult woman, original character, alchemist, long green wool coat, leather apron, long sleeves, holding a glass '
             'flask up with right hand, left hand on an open book, fingers, workshop, shelves of jars, warm window light, upper body',
     'prose': 'Anime illustration of an adult woman alchemist, an original character in a long green wool coat and leather apron, '
              'holding a small glass flask up to the light in her right hand while her left hand rests flat on an open book, all ten '
              'fingers visible, cluttered tower workshop with shelves of jars, warm window light, upper body'},
]


def by_id(name): return next(s for s in SUITE if s['id'] == name)


def negative_tags(case, base):
    """Model negative plus the SFW/adult-only terms (always added; the rule is strict for fanservice prompts)."""
    return base + ', ' + SFW_NEG_TAGS
