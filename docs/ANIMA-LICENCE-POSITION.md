# Anima licence position

Written 1 November 2026 at the owner's request, to record what the terms say, how this project uses the models and what was
decided. This is a project record, not legal advice. A completed render and an accepted picture are separate things from
this: this page covers only the licence state.

## What it covers

| Item | Library pin | Licence |
| --- | --- | --- |
| Anima Base v1.0 | `anima-base-v1-0` | CircleStone Labs Non-Commercial License; derivative of NVIDIA Cosmos-Predict2 under the NVIDIA Open Model License |
| Anima Turbo v1.1 | `anima-turbo-v1-1` | Same |
| Anima Aesthetic v1.1 | `anima-aesthetic` | Same family; read its own library entry |
| Reference adapter v2 r64 | `anima-ref-adapter-v2-r64` | CircleStone Labs Non-Commercial License v1.2, a Derivative. Its node code is Apache-2.0 |

## What the terms say

Sources, read 1 November 2026: the
[adapter's LICENSE.md](https://huggingface.co/ElectronGirl/anima-ref-adapter/blob/b729afd0c3307f27438df42697ccafaecf051d26/LICENSE.md)
and the [Anima model card](https://huggingface.co/circlestone-labs/Anima). The card was read at `main`; the model files are
pinned to revision `f973fc41`. Paraphrased here, so read the originals before relying on any line.

- **Pictures.** The licensor claims no ownership of outputs, and section 2(e) lets you use them for any purpose, commercial
  included, except where the licence expressly prohibits it. The model card agrees, and gives selling images and paid commissions
  as allowed examples.
- **The models themselves.** They are for non-commercial purposes only (sections 1(c), 2(b), 4(a)(i)). The card names hosting
  behind a paid API and embedding in a monetised game as needing a separate licence. Internal testing and evaluation by a
  company is a non-commercial purpose.
- **Sharing the weights.** Anyone given a copy must get the licence, with the attribution notice (section 3).
- **Breach.** The licence ends automatically on breach, and all use must then stop (section 8).

Two loose ends in the text. Section 1(c) also says use for revenue-generating activity is not a non-commercial purpose, which sits
awkwardly beside section 2(e); the card's explicit examples are the plainest statement of intent and favour output use. Section
4(a)(i) points to section 2(d) for outputs, though outputs are in 2(e), which looks like a numbering slip.

## How this project uses them

- Models run only on the owner's own PC. The Studio listens on loopback. Nothing is hosted for anyone else.
- The weights are not in this repository, not redistributed and not embedded in any shipped product.
- There are no commercial plans today. The owner said so on 15 September 2026 (see `HUMAN_TODO.md`, Recorded owner decisions)
  and again on 1 November 2026.
- Every model is pinned by hash in `models/library.json`, and every preset's `commercial_note` carries its terms.

## Owner's decision

On 1 November 2026 the owner chose "Commercial use allowed" for question `anima-ref-terms-1101`, and added, in their own words:
"with the caveat that we're not really doing anything commercial for now anyway. Essentially I just want to not worry about this
for now, just document things somewhere it gives me a defensible and strong stance in case of sticky situations, but that's it".

Agents read that as: no restriction on using these presets now, and pictures made with them may be used as section 2(e) allows.
It does not change what the licence says about the models.

## If anything changes

Check again before any of these, and ask the licensor through the contact on the model card if the answer is not clear:

- Putting a model, the adapter or a merge of them inside a paid product, a game build or a paid service.
- Letting other people generate through this setup.
- Training or fine-tuning other models for commercial use on these weights or their outputs.
- Sharing the weights with anyone.
