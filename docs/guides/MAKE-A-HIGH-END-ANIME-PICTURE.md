# Make a high-end anime picture

This guide takes you from "I want a very good anime picture" to a picture you can keep, using Make. It uses the button names you see on screen. It was written from the Make page as built on 16 October 2026 (`app/static/make.js`, after Make wave 5) and from the [look lab of the same day](../looks/LOOK-LAB-2026-10-16.md). Rounds 3 to 5 (poses, adapters, finishing, restyle and game icons) are in that report.

**What this guide does not claim.**

- It does not say any look is high-end, beautiful or ready to publish. The lab measured whether the things you ask for survive in the picture. It did not measure taste.
- The lab judges were agents, on this PC, on a handful of scenes. They are not you, and they are not art acceptance.
- Nothing here clears a licence. Every model and adapter has its own terms. See [Licences](#licences-read-this-before-selling-anything).

## 1. The four-step happy path

You need the Studio and ComfyUI running. On the configured PC, `Start Studio.cmd` does both.

1. **Open Make.** In the sidebar, under Workspace, press **Make**. **Anime character** is already chosen on a fresh browser. If not, press it.
2. **Pick the look.** The first card is **Flat pastel close-up**. Press it. The card list folds to one line and the words box opens below it, with your pictures beside it on a wide window.
3. **Describe it.** Under **Describe your picture**, answer "Who or what, doing what, where?". Plain words are fine. The look adds its own style and quality words. Press **Use the example** if you want a starting sentence you can edit. Do not paste model tags such as `masterpiece`: the look writes those.
4. **Press Generate** (or Ctrl+Enter in the words box). Nothing runs until you press it. A line under the button says how long it should take, from earlier runs on this PC. The default is **4 to choose from**, or **1 picture** for a slow look.

Your pictures appear under **Your pictures** as they finish. Press **Keep** on the ones you like and **Not this** on the rest (section 4).

What you just used: **Flat pastel close-up** is the Anima model with the PetiFlow adapter. Its wording asks for flat colours, a face-focus, upper-body, close-up framing and an adult character. Ask for a portrait or a bust for the best measured results. A medium shot or a standing full-body scene also held the look in the lab, on some seeds (section 2). If you want something glossier, go to section 2.

Press Ctrl+K at any time for the tool finder. It searches goals, looks and tools by the names on the cards. It only moves you around: it never starts a picture. It matches the card names, not model names: search "pastel", not "PetiFlow".

## 2. Choosing a look

### What the card tells you

- **Name.** It describes the finish, not the model. The model name is under **What this look uses** (below Generate).
- **Speed label.** It shows a measured median per picture: this PC's finished runs of the look, or if there are none, the lab. "Fast · ~31 s" is under 45 seconds, "Medium · ~N s" is under 3 minutes, and "Slow · ~N min" is 3 minutes or more. A look with no timing yet says "Speed not measured yet". A Krea look with no number says "Slow · several minutes". Hover the label for its source. In the lab, Krea pictures took 6 to 37 minutes, so treat Krea minutes as a floor.
- **Tested well.** The look kept its named subject and props in at least 3 of 4 lab pictures, or 2 of 2 where only two were made. Hover the badge for the exact count. It means an agent liked how the lab pictures matched the brief. It is not art approval and not licence clearance. A look without the badge is not bad. It was not kept often enough, or it was not tested the same way.
- **Best for.** A short line on the tested looks saying what that look carried in the lab, for example "Close-ups and upper-body portraits holding one thing". It is a note from the lab, not a promise.
- **Non-commercial.** A tag shown only on a look whose own recipe note (`commercial_note` in `presets/catalog.json`) names non-commercial terms, so it appears on some Anima-based looks and the NoobAI look but not on every look built on those models. For example, **Flat pastel close-up** carries no tag because its recipe note records no terms, even though its Anima model is non-commercial (see Licences). No tag is not clearance, and the tag is not a licence check. See [Licences](#licences-read-this-before-selling-anything).
- **Run on this PC before.** The recipe behind the look has an executed record here.

### The Anime character looks, in the order Make lists them

The lab numbers are from [the lab report](../looks/LOOK-LAB-2026-10-16.md). "Seconds" is the median per image, including model loading. Your times will differ.

| Card name | Model (and adapter) | Seconds | Lab result |
| --- | --- | ---: | --- |
| **Flat pastel close-up** (Tested well, 4 of 4) | Anima base + PetiFlow adapter at 1.0 | 31 | Both first-round pictures kept. A florist holding a bucket: kept on both new seeds. Handle of the bucket not visible. Best measured first choice for this goal. |
| **Magazine-cover anime, soft focus** | One Obsession Anima v2.0 | 31 | One kept, one fixable (a closed parasol came out open). On a new scene, one of two seeds kept; the other put large garbled magazine lettering on the picture. |
| **Crisp artist-style anime, cinematic light** | AniFox v2 + Ringeko adapter at 0.8 | 45 | Both first-round pictures kept, with readable faces and a held cat or fox. On a new librarian scene, 0 of 2: both added a book with garbled text. It lost its Tested well badge. |
| **Glossy showcase anime, sparkling colour** | Pearly Anima Mix v1.0 | 30 | One kept (adult mage, staff, meadow). The default magical-girl scene read as youthful and was skipped, so do not use that default as an adult character. On a new astronomer scene, 0 of 2: the hands split onto two instruments. |
| **Glowing fantasy anime, light rays** | WAI v17 | 25 | One kept, one fixable: a brass wrench came out silver and a glove became a mitten. |
| **Modern anime portrait, bronze and moss green** | Anima aesthetic v1.1 | 37 | One kept, one fixable: a star chart sat on an easel instead of being held. |
| **Clean anime portrait, rim light** | Animagine XL 4.0 | 42 | Both rejected: a named prop was missing or wrong. |

How to read this:

- The lab is two to four pictures per look. It cannot rank them. The lab report says differences under 0.3 on its score are ties.
- Specific held objects fail more often than faces. Check hands, props and any written words in every picture.
- **Flat pastel close-up** also held its look at medium shot (2 of 2 seeds: head to hips, elbows and waist visible) and at full body (1 of 2 seeds). The seed that failed added camera-like fixtures to the greenhouse sides, so check the background as well as the figure.
- The lab did not test which look is "high-end". If you want to choose by eye, use **Compare looks** (section 4).

Painted looks (oil, ink, watercolour) are under **Painted illustration**, and the Krea ones take minutes per picture. They are a different journey.

### Game items

The **Game item or icon** goal has **Painted game icon**, which draws one named object on a white background. In the round-5 lab it always drew one item (6 of 6 trials), but its shape details often drifted. Only 1 of 6 trials on new objects was a strict keep: the backpack, on its default seed. The shield, crystal and key were fixable. Both shield seeds turned the requested round outline into a pointed heraldic shield. Both crystal seeds added a rounded-square frame. The key had two teeth instead of three.

The card can show **Tested well**, because of the two round-4 objects (a potion and a sword, one seed each). That badge does not cover a new object. Check the shape, the count and any frame or border in every picture before you use it. The lab did not prove exact white, transparency, small-icon readability or a game-engine import.

## 3. Getting the right model and adapters

### See what a look uses

Under Generate, open **What this look uses**. It lists the **Model** (with its file), then each **Adapters** line with its strength and its trigger word. The look already writes its own trigger words into your text.

### Tune this look

Open **Tune this look** under the words box. It is folded by default. The line next to it summarises your changes, for example "Tuned: model One Obsession Anima v2.0 · Ringeko 0.6". Tuning only changes what **Generate** sends. It never runs anything on its own. The server still checks every value against its own allow-list and ranges.

**Model**

- **Base model** switches the model while keeping the look's words and adapters. The list holds only models of the same type (same loader and text encoders), so the words still fit. **As made** is the first entry. Pictures will differ.
- For **Flat pastel close-up** the list is the other Anima models in the library. On the SDXL looks (WAI, Animagine, AniFox) it also lists other SDXL models, and **NoobAI XL 1.1** is currently one of them. See [Licences](#licences-read-this-before-selling-anything).
- An entry that ends "needs download" has missing files. A line below the list says so and links to **Models & setup**.
- The lab did not test switching the model under an adapter. Treat it as an experiment: change one thing, then compare.

**Adapters (LoRAs)**

- Each row has a tick (on or off), the adapter name, a strength slider from 0 to 2, **Remove**, and a note: its trigger word, "No trigger word", or "Fixed in this recipe".
- Strength 0 turns an adapter off. The Studio removes it from the picture's recipe.
- **Add an installed adapter**: type part of a name, choose it from the list, press **Add**. Only adapters that are installed and known to fit this model type are listed. The strength starts at the adapter's usual value, or, for the Petiflow adapters the lab tested, at the lab's neutral value (see above).
- If you add an adapter that has a trigger word, the Studio adds that word to your text for you (the row says "added to your words"). The look's own adapters already have theirs.
- If all adapter slots are in use, **Add** is disabled and the page says "All adapter slots of this recipe are in use; remove one first."
- **Style strength** (under **Shape** and **How many**; with **Tune this look** open, it sits above the adapters instead) scales all the look's adapters together. 100% is the look as made. It multiplies the per-adapter strengths above.
- What the lab saw: PetiFlow at 1.0 and Ringeko at 0.6 and 0.8 worked. Adding a detail, lighting or hand adapter at 0.4 to 0.6 on top of Ringeko did not make a measurable difference on one clean scene. More tags and more adapters were not a proven fix for a missing prop. The lab never tried those extra adapters at 1.0.
- **Adding style adapters to Flat pastel close-up.** On one fern scene (round 3, one seed), the lab added Anima style adapters to PetiFlow at 1.0. At low strength they were neutral: Ke-ta at 0.35 and 0.7, Xilmo at 0.35, NEWANIMASTYLE at 0.5. Ke-ta and Xilmo together, at 0.35 each, were neutral too. At their defaults they were not: Xilmo at 0.7 turned the fern into broad leaves, NEWANIMASTYLE at 1.0 changed the plant and the face, and Kieed at 0.5 (and at 0.25) flattened the face and changed the plant. Ke-ta at its default 0.7 was neutral.
- Make starts the tested ones at the neutral strength and shows the lab note under the row. Kieed has no neutral value in the lab: both 0.5 (its usual start) and 0.25 harmed the face and plant, so leave it off unless you want to experiment.
- Neutral is not better. None of these adapters improved the picture in the lab. Prefer the untuned look unless you want a different flavour.

**Quality and speed, Leave out, Seed**

- **Steps**: **As made**, **Draft** (half the steps, faster) or **Finer** (more steps, slower). More steps are not always better.
- **Sampler**: the other samplers this recipe offers.
- **Leave out**: the negative words, for things to keep out of the picture.
- **Seed**: locked only when **Different pictures each time** is unticked (section 4).
- **Back to the look as made** clears every change at once.

### When something needs a download: Models & setup

If **Generate** is disabled and the reason says "Needs 2 model files first: open Models & setup", press that link. It opens **Models & setup** filtered to "Files needed for" that recipe.

- Each card shows the file, its size, where it comes from, its licence text, and a state such as "SHA-256 verified" or "Not installed".
- If the Studio can install the file, the button reads **Install** with the size. Press it once. Progress shows on the card.
- If it cannot, the card says **Manual install only**, shows the source link and the folder to put the file in, and has **Copy folder** and **Copy file path**. Download it yourself and copy it in. The card for the adapter you added in Tune appears the same way.
- After copying a file, press **Refresh inventory** and check the card reads as present. **Verify** hashes the file and compares it with its pinned checksum.
- Only `.safetensors` files can be installed or verified here. A file of another format, such as a GGUF, reads **Present · pin only** once copied in, and its button stays disabled as **Manual file**. The UI cannot hash it, so it never reads "SHA-256 verified"; compare its checksum with the pin in `models/library.json` yourself.
- The top of **Models & setup** also lists **What you can make**: which looks are ready now and which need a download.

A matching hash proves the bytes match the pinned file. It does not prove who made it or that you may use it commercially.

## 4. Tweaking without losing your place

**Another go, same words.** Press **Generate** again. While **Different pictures each time** is ticked, every press starts from a new seed.

**Change one thing.** Press **Edit and re-run** on a finished card. It brings back that run's words, shape, count, style strength, tune and **seed, locked**, and sets **Different pictures each time** off. The page says "That run’s settings are back, with its seed locked." Change one setting or a few words, then press Generate. Because the seed is the same, what you change is what you see.

**Draft, then the final.** **Draft first** is a tick under the words options: about half the steps, rougher but quicker. It shows on any look with 10 or more steps, and on every slow look (the Krea ones). The anime looks have 25 to 30 steps, so they show it too. You can also set **Steps** to **Draft** under **Tune this look**. Either way:

1. Press **Generate**. The card's tune line reads "Tuned: draft N steps".
2. If you like it, press **Make the final** on the card. It sets up the same words and the same seed at the look's full steps. The page says "The final is set up". It does not start the job: press **Generate** to make it.

The anime looks run in about 25 to 45 seconds a picture in the lab, so a draft earns its place mostly when you change a lot at once.

**Keep or drop.** Under each picture:

- **★ Keep** saves the decision in the library. Once pressed, it shows "✓ Kept". The page says "Kept. Your keepers are in the library under Keepers."
- **Not this** marks it as not wanted. Once pressed, it shows "✓ Marked: not this".
- Press the same button again to clear it. It never deletes the picture.
- In the look gallery there is also a link called **Stay with** followed by the look's name. It appears once a look is chosen. It just closes the gallery and keeps the look. It saves nothing.

**Same words, another look.** On a finished card, press **Same words, another look**. The gallery opens with that scene ready.

**Make this my character…** appears on every finished picture saved in the library, including Compare pictures, whether kept, unreviewed or marked **Not this**. Name the character and save: this picture becomes its canon without making another picture or changing its review. A canon picture says **Canon of** followed by the character's name. The character's **Line-up** keeps the canon first, then kept descendants.

**Compare looks.** In the look gallery, press **Compare looks**. Choose two or three looks, type one scene, and press **Generate** (the button reads "Generate 3 pictures"). Each look runs once, as made, at its own shape, from one seed where its recipe takes a seed. The pictures share one card. If you already picked a look, press **Change look** first to get the gallery back, and **Back to one look** to leave. Compare ignores your Tune changes.

**Vary.** The **Vary** buttons under a picture open the Full editor with new seeds or a nearby variation prepared. They do not run. Press **Generate** there.

**Words that went wrong in the lab.** Say the small relationship words plainly ("holding a closed parasol", "one astrolabe in both hands"). Count hands and props. Look for text you did not ask for: books and magazines got garbled lettering. A wide-shot or scenery tail in a look's words can shrink the face.

## 5. Finishing

### Under each picture

- **Fix face**, **Fix hands and details** and **Upscale 2×**. Each shows an estimated time when the Studio has one. One press starts one job. The result appears at the top of **Your pictures**.
- The face and hand fixes repaint with an anime model, so they are offered only for pictures made by anime families. Upscale accepts any picture. On Anima pictures, **Fix face** and **Fix hands and details** both run the same WAI-based repaint, face then hands.
- A fix that cannot run stays on the picture, greyed out, with its reason in a line beside the buttons. Open the goal **Fix or upscale** to see the same reasons (below).
- **More** holds: **Open full size**, **Other fixes…**, **Change one thing**, **Restyle**, **Put in a new pose**, **Animate**, **Make it 3D**. The goal buttons open that goal with your picture already chosen.

Round 5 of the lab measured these passes on clean pictures, which had no named defect to repair. They show what each pass does to a picture that was already good, not whether it repairs a broken hand or face. The steps below come from that test. Look at the result before replacing your original.

### How to finish a picture

1. **Keep the original.** Open it full size. Check the eyes, both hands, held objects and any lettering before you choose a fix.
2. **Fix face or Fix hands and details** on an anime picture: try one, once. On Anima looks these repaint with a WAI model, and they can change the face finish. In the lab, PetiFlow's soft face and eye colour drifted. Compare the new face, fingers, expression and style with the original. Keep the pass only if the thing that needed fixing got better and nothing important was lost. The lab's fix passes took 37 to 148 seconds each.
3. **Upscale 2×** the version you chose, not the original. Upscale smooths texture, so eyelashes, hair lines, fabric and hands can look softer at full size. It keeps earlier mistakes and cannot repair anatomy. The lab's upscales took 59 to 499 seconds.
4. **Restyle** is a redraw, not a filter. It keeps the character recognisable, but the face, pose and props can drift. In the lab, watercolour transferred better than ink, for both sources. The ink target only partly took its bold brushwork. Run Restyle from the original unless you want the repaired version as its input. Name the colours to keep, and compare the face, pose and props as well as the style. Restyle took 62 to 80 seconds.

### Fix or upscale (a goal)

1. Press **Fix or upscale** in the goals row (under "From a picture you have").
2. Choose the picture. Use the search box if the right one is not in the newest 60.
3. Under **Choose one**, pick **Fix face**, **Fix hands and details** or **Upscale 2×**. An option that cannot run says why under it.
4. Press **Generate**.

### Restyle a picture

1. Press **Restyle a picture**, then choose the picture.
2. Under **Redraw it the way this look is drawn**, choose a look by its picture. Or press **Describe the look in words instead** and fill **Describe the new look**. **Colours to keep (optional)** helps hold hair and clothes.
3. Press **Generate**.

Restyle uses its own restyle recipe, not the look's model. The page says only how the look is drawn is copied, not what it shows. Your picture keeps its character, pose, clothes and layout, within what that recipe can hold. Check the result for drift. **What this uses** names the recipe.

### Character in a new pose

1. Press **Character in a new pose**, choose the character picture.
2. Under **Pose**, choose **A picture of the pose** (pick a library picture) or **Draw the pose** (pick a stick figure, optionally tick **Mirror left and right**).
3. When the pose is a picture, **What to keep** offers three choices when their recipes are available:
   - **Keep my character as it is** (Copy Pose, the default). Your character keeps its face, clothes, background and finish. Only the body position comes from the pose picture.
   - **Put my character into this picture’s scene** (Replace character). The pose picture keeps its outfit, setting and finish. Only your character’s face and hair go in.
   - **Follow the pose picture’s outline (depth)** (optional). Follows the outline closely; in lab round 3 it simplified the face and curls, and one result had a blank grey face. Clothing shapes can carry over and your character may change. It is never the default or an automatic fallback; plain Klein 9B stays hidden.
4. Fill the fields: who is in the picture, what they wear with colours, the pose in a few words.
5. Press **Generate**.

If Copy Pose is unavailable, Make keeps its existing fallback to the next available picture route and says why. A missing optional route uses the same default/fallback path.

**What the lab measured for the picture route:**

- **Keep my character as it is** kept the pose, the face and the finish on 3 of 3 seeds for each of the two Anima pairs in round 4: the Petiflow botanist on One Obsession's flute pose, and the One Obsession musician on Petiflow's pot pose. Each picture took about 90 to 125 seconds. Identity was not exact. Faces drifted, with eyes, freckles or curls changing, so check the face every time.
- It also worked with a Z-Image source (one picture, one seed, KEEP). That source's own stance missed its brief, with the hands hanging by the thighs, so check the stance too.
- **WAI sources needed a hand repair.** On the WAI older man, Keep my character as it is was fixable, because the foreground fingers formed an awkward grip. The same WAI source with Put my character into this picture’s scene was a KEEP.
- **Put my character into this picture’s scene** swapped the character into the pose picture's outfit and setting. On the two Anima pairs it was 2 of 2 KEEP in round 3, and on the WAI and Z-Image sources it was KEEP in round 4. The outfit and setting are the pose picture's by design, so do not expect your character's clothes to come back.

**Hands and wording:** a drawn figure follows the body but not hand words. In round 3, both standing outputs ignored "relaxed closed hands". Describe the pose simply: the body position, the held object by name, and the camera. Do not rely on a finger count.

A stick figure carries the pose and nothing else. To move single joints, use **Open in the full editor instead**. In the lab, a drawn pose controlled the body. It did not prove that the same character came back, and it does not control fingers. Treat identity and outfit as something to check, not something to trust.

## 6. When to open the Full editor

Make covers a look, its tune, the shape and the count. Open the Full editor when you need:

- sampler, scheduler, CFG or denoise by hand;
- more adapter slots than the look shows, or a recipe that is not a look;
- a reference board (identity, pose or style pictures);
- **Plan comparison** for a budgeted, blind comparison (see **Compare & review**);
- the recipe's graph under **Under the hood**, or **Open ComfyUI**.

Two ways in:

- **Open in the full editor instead**, under Generate in Make. It prepares the same request Generate would send, with your words filled in, and shows it. It does not generate. Press **Generate** there, or Ctrl+Enter.
- Sidebar: **Advanced**, then **Full editor**. The Advanced group is folded until you open it.

Use **Make** in the sidebar to come back. **Compare & review** (also under Advanced) is for budgeted plans, not for Make's **Compare looks**.

## 7. Troubleshooting

### A button is disabled

Read the line under **Generate**. It says why. The same text is the button's tooltip. Common reasons, exactly as shown:

| You see | What to do |
| --- | --- |
| Needs N model file(s) first: open Models & setup. | Section 3, Models & setup. |
| ComfyUI is not reachable. Start it, then try again. | Start ComfyUI, for example with `Start Studio.cmd`. |
| ComfyUI is still starting up. Try again in a moment. | Wait. |
| A model environment switch is running. Wait for it to finish. | Wait. |
| The Studio worker has stopped. Restart the Studio before generating. | Close and reopen the Studio. Make sure nothing is running first. |
| This look’s recipe is not in the library. | The look points at a recipe that is not installed. Pick another look. |
| Choose at least two looks to compare. | Compare looks needs two or three. |

If Generate is enabled and you press it with an empty box, the page says "Describe your picture first, or press Use the example." and puts the cursor in the box.

### The words on a card

| Card says | Meaning |
| --- | --- |
| Waiting its turn, Waiting for memory | Studio runs one job at a time. Others wait. Do not press Generate again. |
| Sending, Painting | Running. You can leave the page. Make remembers your last six runs. |
| Done | All pictures finished. |
| Did not finish | Failed. The reason is on the card. |
| Some pictures did not finish | Partial. The ones that finished are shown. |
| Cancelled, Not sent | It was not run. |
| Saving to the library… | The picture exists and is being registered. Keep, Not this and fixes appear when it is done. |

### Outcome unknown

If the card reads **Outcome unknown: nothing was sent again**, the Studio lost the answer from ComfyUI. It records the job as uncertain and will not run it again by itself. That is on purpose. A job whose result is unknown may already be running or finished.

- Do not press **Generate** again for the same picture to "retry".
- Keep the card. The prompt ID and the full recipe are saved under `experiments/runs/<job-id>/`.
- The run's card offers **Resume observation** and **Stop tracking…** on an uncertain or partial run, when the Studio still has its prompt IDs. **Resume observation** reads ComfyUI again and collects the result if ComfyUI still holds it. It never sends the picture again.
- **Stop tracking…** opens a reason box. The reason is required: the button will not stop tracking without one. A ComfyUI restart erases a finished result, so press **Resume observation** first if you may want it.
- The Full editor's **Problems** list has the same two controls.
- Details are in [Operations](../OPERATIONS.md) ("Uncertain submission").

### Other things

- **Slow.** The line under Generate gives an estimate from earlier runs. "No timing yet" means the look has not run here at this size. Krea looks are the slow ones.
- **Pictures missing after a reload.** Make restores your last six runs from their job records. Older ones are in the library: **Open the library**.
- **The words I typed are gone.** The words box is remembered per goal for the browser session, not forever.
- **Nothing happens on page load.** That is by design. Only **Generate** submits.

## Licences: read this before selling anything

The Studio records each model's and adapter's terms. It does not interpret them for you. A flag copied from a download page is not a clearance. Read the owner's page before commercial use. Each card in **Models & setup** shows the short licence line only. The longer terms the manifest records for a file (its `terms` field, such as a model card's licence name and revision) are in `models/library.json`, not on the card, so read them there.

For the path in this guide:

- **Anima** (the model family under **Flat pastel close-up**, **Magazine-cover anime**, **Glossy showcase anime** and **Modern anime portrait**): the catalog note on the Anima artist-stack recipe says CircleStone Labs Non-Commercial model weights, and the library notes on the One Obsession and Pearly merges say those base terms also apply. Treat the whole family as non-commercial unless you have read the terms yourself.
- **PetiFlow adapter**: the recorded flags list RentCivit and Rent, not Sell, with credit not required and derivatives allowed. That is a record of a listing on 21 September 2026, not a licence check.
- **NoobAI**: its licence excludes commercial products. It is the base of the Scene look **Wide fantasy scenery, glowing light** and it is offered as **NoobAI XL 1.1** in **Base model** for the SDXL anime looks. Anything made with it stays hobby and research only, whatever the adapters allow.
- **Ringeko** (AniFox look): an artist-style adapter. Its record says derivatives are not allowed. It is not a grant to any character or artist.

## Where to go next

- [Anime and fantasy atelier](../ANIME-FANTASY-ATELIER.md): every recipe and adapter with trigger words, terms and timings.
- [Look lab, 16 October 2026](../looks/LOOK-LAB-2026-10-16.md): the evidence behind section 2, and its limits.
- [Start here](../START-HERE.md): the short first-picture walkthrough in Make.
- [Operations](../OPERATIONS.md): installing models, uncertain submissions, troubleshooting.
