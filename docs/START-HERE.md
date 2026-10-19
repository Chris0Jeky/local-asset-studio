# Your first picture

This page gets you from a closed Studio to one picture in about five minutes of your own time, then points you to the next thing to learn. It describes **Make**, the first screen. Button names are the ones on screen.

It does not say any picture is good, finished or cleared for sale. A completed run only means ComfyUI finished it. You judge the picture. Model and adapter terms are a separate question: see [Model terms](../README.md#model-terms-and-local-only-media).

## 1. Start the Studio

Double-click the **Asset Studio** desktop shortcut, or run `Start Studio.cmd` in the repository folder. The launcher starts ComfyUI if it is not running, then starts the Studio and opens `http://127.0.0.1:8191`. Give it time: the first start is slow.

- The Studio listens on `127.0.0.1:8191` only. It is not reachable from other computers.
- ComfyUI itself runs on port 8188.
- The page opens on **Make**. A fresh browser has **Anime character** already chosen. Make remembers your last goal and look in that browser.

## 2. Make a first picture

1. **Pick a goal.** The row at the top lists what you can make. For a first picture, keep **Anime character**. The other goals that start from words are **Scene or background**, **Painted illustration**, **Photo** and **Game item or icon**.
2. **Pick a look.** A look is a ready-made recipe: the model, its adapters and its settings, with its own style words already written. Press the card whose picture you like. Each card shows:
   - **Speed.** For example "Fast · ~31 s" or "Medium · ~163 s". The number is a median measured on this PC, from your own finished Make runs of that look or else from the 16 October 2026 look lab. Hover the line to see which. "Speed not measured yet" means no timing exists.
   - **Tested well**, **Best for** and **Non-commercial** where they apply. **Tested well** means an agent kept most of that look's lab pictures. It is not art approval and not licence clearance. **Non-commercial** is copied from the recipe's own note.
   - **Run on this PC before**, if the recipe has an executed record here.
   - A warning in red if the look cannot run yet, for example "Needs 2 model files first: open Models & setup".

   The first card for **Anime character** is **Flat pastel close-up**. After you press a card, the gallery folds to one line, "Look: …", with **Change look** beside it.
3. **Describe your picture.** Answer "Who or what, doing what, where?" in plain words. Press **Use the example** for a starting sentence you can edit. Do not add model tags such as `masterpiece`: the look adds its own style and quality words.
4. **Press Generate.** This is the only press that sends anything. Nothing runs when the page loads. The line under the button says how long it should take, from earlier runs on this PC. **How many** defaults to "4 to choose from", or to 1 picture on a slow look. Ctrl+Enter in the words box does the same as Generate.
5. **Wait, then choose.** Your pictures appear under **Your pictures** as they finish. You can leave the page: Make remembers your last six runs. Press **Keep** on a picture you want and **Not this** on one you do not. Pressing the same button again clears the mark. Neither deletes anything. Kept pictures are in the library under **Keepers**.

If **Generate** is greyed out, read the line under it. It says why, and the same text is the button's tooltip. If a model file is missing, that line links to **Models & setup**.

First loads are slower than later ones. A long run is not a hang: the card shows "Waiting its turn", "Waiting for memory", "Sending" or "Painting".

## 3. After the first picture

Under each finished picture:

- **Keep** and **Not this**, as above.
- **Vary**, where it is offered. It opens the Full editor with variations prepared. It does not run them; press **Generate** there.
- **Fix face**, **Fix hands and details** and **Upscale 2×**, each with an estimate when the Studio has one. One press starts one job and the result appears at the top of **Your pictures**. A fix that cannot run on that picture stays visible and greyed out, with its reason beside it.
- **More**: **Open full size**, **Other fixes…**, **Change one thing**, **Restyle**, **Put in a new pose**, **Animate** and **Make it 3D**. These open the matching picture goal below with your picture already chosen.

On the picture's card:

- **Edit and re-run** brings back that run's words and settings with its seed locked. Change one thing, press **Generate**, and what you changed is what you see.
- **Same words, another look** reopens the gallery with that scene ready.
- **Make the final** appears on a run made at **Quality: Draft**. It sets up the same words and seed at the look's full steps. It does not start the run: press **Generate**.

Under the words box:

- **Model, LoRAs and settings** is folded shut. Open it to see and change the look's base model, adapters (LoRAs) with their strengths, steps, sampler, words to leave out and seed. It only changes what **Generate** sends.
- **Quality** (Draft, As made, Fine) is offered on looks with ten steps or more, and on slow looks. A draft uses half the steps: rougher but quicker. Fine uses half as many again: slower. On Anima looks Draft is the official turbo LoRA at 8 steps (cfg 1, euler/simple; about 13 s warm, a near-tie with a full run in the 19 Oct lab) and there is no Fine, because 20 to 40 steps looked alike.
- **What this look uses** names the model and adapters, with each adapter's trigger word.
- **Shape**, **How many** and **Style strength** are beside the Generate button.
- **Compare looks**, in the look gallery, runs two or three looks on one scene and one seed and shows them side by side.

### If a card says "Outcome unknown"

The Studio lost the answer from ComfyUI. The card says nothing was sent again, and that is deliberate: the picture may be running or finished. Do not press **Generate** again to retry. Use **Resume observation** on the card to ask ComfyUI again for the saved prompt IDs. **Stop tracking…** asks for a reason and records it. ComfyUI keeps a finished result only in memory, so after a ComfyUI restart **Resume observation** cannot collect it. See [Operations](OPERATIONS.md).

## 4. Start from a picture you already have

Under "From a picture you have", the goals take a picture instead of words. Choose the picture (search the box if it is not among the newest 60; use the library's import first if it is not there), answer the one or two fields, and press **Generate**.

| Goal | What it does |
| --- | --- |
| **Change a picture** | Changes one thing and keeps the rest. Say only the change, for example "replace her hat with a red Santa hat". |
| **Fix or upscale** | **Fix face**, **Fix hands and details** or **Upscale 2×**. |
| **Restyle a picture** | Redraws the picture in another look, chosen by its picture or described in words. It keeps the character, pose, clothes and layout as far as the recipe can hold them. |
| **Character in a new pose** | Takes a character picture and a pose, either a picture of the pose or a drawn stick figure. A stick figure carries the pose and nothing else. |
| **Animate a picture** | A short clip from a still. Say how it should move. Video results have failed inspection so far: see [Status](STATUS.md). |
| **Picture to 3D** | Cuts the background away and builds a draft 3D model (GLB) to inspect. Hidden sides are guessed. |

**What this uses**, under each, names the recipe that will run. None of these promises that unedited areas stay pixel-identical, or that a face or costume survives. Look at the result before replacing your original.

## 5. Where to go next

- **The detailed guide.** [Make a high-end anime picture](guides/MAKE-A-HIGH-END-ANIME-PICTURE.md) goes through choosing a look, tuning model and adapters, drafts, finishing and troubleshooting, with the look lab's evidence and its limits. It also lists the licence questions.
- **Every setting: the Full editor.** In the sidebar, open **Advanced**, then **Full editor**. You get every recipe, reference slots, sampler, scheduler, CFG, denoise, and the recipe's graph. Use **Change recipe** in its Run setup panel to pick any recipe, not only a look. **Open in the full editor instead**, under Generate in Make, loads your current request there without running it. Come back with **Make** in the sidebar.
- **Downloads and missing files: Models & setup.** It shows which looks are ready, which files each needs, where each comes from and where it goes. A matching hash shows the bytes are the pinned ones. It does not show who made the file or that you may use it commercially.
- **Your pictures: Library.** Import, tag, review and reuse everything the Studio has saved.
- **The tool finder.** Press Ctrl+K (or **Jump to a tool**) and type a word such as "upscale", "pose", "pixel" or "download". It lists goals, looks and tools by the names on screen. It only takes you there. It never starts a picture.
- **Other pages.** [Anime and fantasy atelier](ANIME-FANTASY-ATELIER.md) lists every recipe and adapter with trigger words, terms and timings. [Experiments and native finishing](EXPERIMENTS.md) covers budgeted comparisons and Krita, Godot and Blender handoffs. [Operations](OPERATIONS.md) covers installs, uncertain jobs and troubleshooting.

## Four words that help

**Prompt** describes the picture: subject, medium, framing, lighting, background and useful exclusions. In Make you type only the scene. The look adds the rest.

**Seed** selects the starting noise. Keep it fixed when comparing one change. In **Model, LoRAs and settings**, untick **Different pictures each time** to lock it. The same seed on different models does not give the same composition.

**Steps** is the number of sampling passes. More steps take longer and are not always better. Each look and recipe has its own default. Do not set every model to 40. In **Model, LoRAs and settings**, **Steps** offers **As made**, **Draft** and **Finer**.

**CFG** sets how strongly the prompt guides sampling. High values can damage a picture, so begin with the recipe's value. **Denoise**, on image variations, sets how much freedom the model gets to change the original. Both are in the Full editor.

## Things worth knowing before a long render

- **Adapters (LoRAs).** Strength 0 means off, and the adapter is removed from the graph. Most style adapters need their trigger word to do anything. Make writes it for you when you add an adapter in **Model, LoRAs and settings**.
- **Wildcards.** In a prompt, `{misty|stormy|golden}` picks one option and `__lighting__` picks a line from `presets/wildcards/lighting.txt`. The server chooses when it sends the job, from the seed, so the same recipe and seed give the same prompt.
- **Krea 2 looks are slow here.** In the 16 October 2026 look lab, they took 6 to 37 minutes per picture on this PC. An earlier single run, 768×1152 at 15 steps, took 986.6 s on 12 September 2026 (see the [timing table](ANIME-FANTASY-ATELIER.md#timing-reality)). Most other anime looks took about 25 to 45 s per picture in the lab. These are one PC's measurements, not benchmarks.
- **Pose-guide recipes in the Full editor.** **WAI • pose guide**, **Animagine • pose guide** and the drawn-skeleton WAI recipe expect a coloured OpenPose skeleton, not an ordinary photo. The **Style + Pose** recipes are the opposite: give them an ordinary picture of a person in the pose and their graph extracts the skeleton. Pose control sets structure. It does not lock face, costume or identity.
- **ComfyUI's own editor.** Use the **ComfyUI** link only when you want to see the graph. Drag a JSON from `workflows/comfyui/` onto its canvas. API JSON in `workflows/api/` is for programs. The chain is load model, encode prompt, sample, decode, save image. The Studio's controls are shortcuts to those same inputs. Save a changed graph under a new name.

## Find your work

- **Your pictures** in Make shows the latest runs. The library keeps every saved picture and survives a reload.
- `experiments/runs/<job-id>/` keeps each job's settings, seed, the exact submitted graph and the execution record, on this PC. On the configured PC `experiments_root` in `config/local.json` decides where that folder is, so back that path up. See [Operations](OPERATIONS.md).
- Full-resolution outputs also stay in ComfyUI's `output` folder. The Studio shows and downloads them.
- Named browser setups are convenience copies. Export a recipe for a durable backup.
- GitHub receives curated experiments only when you copy them into `experiments/curated/` and commit them. Nothing uploads automatically.
