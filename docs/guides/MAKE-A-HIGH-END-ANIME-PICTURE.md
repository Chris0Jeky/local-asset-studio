# Make a high-end anime picture

This guide takes you from "I want a very good anime picture" to a picture you can keep, using Make. It uses the button names you see on screen. It was written from the Make page as built on 16 October 2026 (`app/static/make.js`) and from the [look lab of the same day](../looks/LOOK-LAB-2026-10-16.md).

**What this guide does not claim.**

- It does not say any look is high-end, beautiful or ready to publish. The lab measured whether the things you ask for survive in the picture. It did not measure taste.
- The lab judges were agents, on this PC, on a handful of scenes. They are not you, and they are not art acceptance.
- Nothing here clears a licence. Every model and adapter has its own terms. See [Licences](#licences-read-this-before-selling-anything).

## 1. The four-step happy path

You need the Studio and ComfyUI running. On the configured PC, `Start Studio.cmd` does both.

1. **Open Make.** In the sidebar, under Workspace, press **Make**. **Anime character** is already chosen on a fresh browser. If not, press it.
2. **Pick the look.** The first card is **Flat pastel close-up**. Press it. The card list folds to one line and the words box opens below it, with your pictures beside it on a wide window.
3. **Describe it.** Under **Describe your picture**, answer "Who or what, doing what, where?". Plain words are fine. The look adds its own style and quality words. Press **Use the example** if you want a starting sentence you can edit. Do not paste model tags such as `masterpiece`: the look writes those.
4. **Press Generate** (or Ctrl+Enter in the words box). Nothing runs until you press it. A line under the button says how long it should take, from earlier runs on this PC. The default is **4 to choose from**.

Your pictures appear under **Your pictures** as they finish. Press **Keep** on the ones you like and **Not this** on the rest (section 4).

What you just used: **Flat pastel close-up** is the Anima model with the PetiFlow adapter. Its wording asks for flat colours, a face-focus, upper-body, close-up framing and an adult character. Ask for a portrait or a bust. A full-body action scene fights the look's own words. If you want something glossier or wider, go to section 2.

Press Ctrl+K at any time for the tool finder. It searches goals, looks and tools by the names on the cards. It only moves you around: it never starts a picture. It matches the card names, not model names: search "pastel", not "PetiFlow".

## 2. Choosing a look

### What the card tells you

- **Name.** It describes the finish, not the model. The model name is under **What this look uses** (below Generate).
- **Pace line.** "Fast" or "Fast · about half a minute" for the anime looks. "Finest detail · slow, about 10-17 min" for Krea looks. Treat the minutes as a floor: in the lab, Krea pictures took 6 to 37 minutes.
- **Tested well.** The look kept its named subject and props in at least 3 of 4 lab pictures, or 2 of 2 where only two were made. Hover the badge for the exact count. It means an agent liked how the lab pictures matched the brief. It is not art approval and not licence clearance. A look without the badge is not bad. It was not kept often enough, or it was not tested the same way.
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
- The lab did not test which look is "high-end". If you want to choose by eye, use **Compare looks** (section 4).

Painted looks (oil, ink, watercolour) are under **Painted illustration**, and the Krea ones take minutes per picture. They are a different journey.

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
- **Add an installed adapter**: type part of a name, choose it from the list, press **Add**. Only adapters that are installed and known to fit this model type are listed. The strength starts at the adapter's usual value.
- If you add an adapter that has a trigger word, the Studio adds that word to your text for you (the row says "added to your words"). The look's own adapters already have theirs.
- If all adapter slots are in use, **Add** is disabled and the page says "All adapter slots of this recipe are in use; remove one first."
- **Style strength** (beside **Shape** and **How many**) scales all the look's adapters together. 100% is the look as made. It multiplies the per-adapter strengths above.
- What the lab saw: PetiFlow at 1.0 and Ringeko at 0.6 and 0.8 worked. Adding a detail, lighting or hand adapter at 0.4 to 0.6 on top of Ringeko did not make a measurable difference on one clean scene. More tags and more adapters were not a proven fix for a missing prop. The lab never tried those extra adapters at 1.0.

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
- The top of **Models & setup** also lists **What you can make**: which looks are ready now and which need a download.

A matching hash proves the bytes match the pinned file. It does not prove who made it or that you may use it commercially.

## 4. Tweaking without losing your place

**Another go, same words.** Press **Generate** again. While **Different pictures each time** is ticked, every press starts from a new seed.

**Change one thing.** Press **Edit and re-run** on a finished card. It brings back that run's words, shape, count, style strength, tune and **seed, locked**, and sets **Different pictures each time** off. The page says "That run's settings are back, with its seed locked." Change one setting or a few words, then press Generate. Because the seed is the same, what you change is what you see.

**Draft, then the final.** Slow looks (the Krea ones) show a **Draft first** tick under the words options: about half the steps, rougher but quicker. On the fast anime looks there is no such tick. Use **Tune this look**, **Steps**, **Draft**. Either way:

1. Press **Generate**. The card's tune line reads "Tuned: draft N steps".
2. If you like it, press **Make the final** on the card. It sets up the same words and the same seed at the look's full steps. The page says "The final is set up". It does not start the job: press **Generate** to make it.

The anime looks run in about 30 seconds, so a draft earns its place mostly when you change a lot at once.

**Keep or drop.** Under each picture:

- **Keep** saves the decision in the library. The button changes to "Kept". The page says "Kept. Your keepers are in the library under Keepers."
- **Not this** marks it as not wanted. The button changes to "Marked: not this".
- Press the same button again to clear it. It never deletes the picture.
- In the look gallery there is also a link called **Keep** followed by a look name. That one just closes the gallery and keeps the look. It saves nothing.

**Same words, another look.** On a finished card, press **Same words, another look**. The gallery opens with that scene ready.

**Compare looks.** In the look gallery, press **Compare looks**. Choose two or three looks, type one scene, and press **Generate** (the button reads "Generate 3 pictures"). Each look runs once, as made, at its own shape, from one seed where its recipe takes a seed. The pictures share one card. If you already picked a look, press **Change look** first to get the gallery back, and **Back to one look** to leave. Compare ignores your Tune changes.

**Vary.** The **Vary** buttons under a picture open the Full editor with new seeds or a nearby variation prepared. They do not run. Press **Generate** there.

**Words that went wrong in the lab.** Say the small relationship words plainly ("holding a closed parasol", "one astrolabe in both hands"). Count hands and props. Look for text you did not ask for: books and magazines got garbled lettering. A wide-shot or scenery tail in a look's words can shrink the face.

## 5. Finishing

### Under each picture

- **Fix face**, **Fix hands and details** and **Upscale 2×**. Each shows an estimated time when the Studio has one. One press starts one job. The result appears at the top of **Your pictures**.
- The face and hand fixes repaint with an anime model, so they are offered only for pictures made by anime families. Upscale accepts any picture.
- If a fix button is missing, the Studio decided it cannot run on that picture and hid it. Open the goal **Fix or upscale** to see the reason (below).
- **More** holds: **Open full size**, **Other fixes…**, **Change one thing**, **Restyle**, **Put in a new pose**, **Animate**, **Make it 3D**. The goal buttons open that goal with your picture already chosen.

The lab did not measure these fixes. Look at the result before replacing your original.

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
3. Fill the fields: who is in the picture, what they wear with colours, the pose in a few words.
4. Press **Generate**.

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
| This look's recipe is not in the library. | The look points at a recipe that is not installed. Pick another look. |
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

If the card reads **Outcome unknown**, the Studio lost the answer from ComfyUI. It records the job as uncertain and will not run it again by itself. That is on purpose. A job whose result is unknown may already be running or finished.

- Do not press **Generate** again for the same picture to "retry".
- Keep the card. The prompt ID and the full recipe are saved under `experiments/runs/<job-id>/`.
- The Make card says to check **Compare & review**. In this build the job's own controls (**Resume observation**, **Stop tracking**) sit in the **Full editor**, under **Recent runs**, in **Problems**. **Resume observation** collects the result if ComfyUI still holds it. A ComfyUI restart erases that record.
- Details are in [Operations](../OPERATIONS.md) ("Uncertain submission").

### Other things

- **Slow.** The line under Generate gives an estimate from earlier runs. "No timing yet" means the look has not run here at this size. Krea looks are the slow ones.
- **Pictures missing after a reload.** Make restores your last six runs from their job records. Older ones are in the library: **Open the library**.
- **The words I typed are gone.** The words box is remembered per goal for the browser session, not forever.
- **Nothing happens on page load.** That is by design. Only **Generate** submits.

## Licences: read this before selling anything

The Studio records each model's and adapter's terms. It does not interpret them for you. A flag copied from a download page is not a clearance. Read the owner's page before commercial use. The terms are in `models/library.json` and on each card in **Models & setup**.

For the path in this guide:

- **Anima** (the model family under **Flat pastel close-up**, **Magazine-cover anime**, **Glossy showcase anime** and **Modern anime portrait**): the catalog note on the Anima artist-stack recipe says CircleStone Labs Non-Commercial model weights, and the library notes on the One Obsession and Pearly merges say those base terms also apply. Treat the whole family as non-commercial unless you have read the terms yourself.
- **PetiFlow adapter**: the recorded flags list RentCivit and Rent, not Sell, with credit not required and derivatives allowed. That is a record of a listing on 21 September 2026, not a licence check.
- **NoobAI**: its licence excludes commercial products. It is the base of the Scene look **Wide fantasy scenery, glowing light** and it is offered as **NoobAI XL 1.1** in **Base model** for the SDXL anime looks. Anything made with it stays hobby and research only, whatever the adapters allow.
- **Ringeko** (AniFox look): an artist-style adapter. Its record says derivatives are not allowed. It is not a grant to any character or artist.

## Where to go next

- [Anime and fantasy atelier](../ANIME-FANTASY-ATELIER.md): every recipe and adapter with trigger words, terms and timings.
- [Look lab, 16 October 2026](../looks/LOOK-LAB-2026-10-16.md): the evidence behind section 2, and its limits.
- [Start here](../START-HERE.md): the older, recipe-first walkthrough in the Full editor.
- [Operations](../OPERATIONS.md): installing models, uncertain submissions, troubleshooting.
