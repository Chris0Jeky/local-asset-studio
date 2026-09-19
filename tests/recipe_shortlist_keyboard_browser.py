"""Focused browser contracts for ordered-source keyboard reordering.

This keeps the timing-sensitive accessibility contract isolated from the much
larger end-to-end shortlist proof. It never calls a backend or generation path.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app" / "static" / "recipe-shortlist.js"
HTML = """<!doctype html><html><body>
<main id="createView"><section id="presetList"></section></main>
</body></html>"""

SOURCES = [
    {"asset_id": "identity", "sha256": "a" * 64, "title": "Identity", "role": "identity"},
    {"asset_id": "pose", "sha256": "b" * 64, "title": "Pose", "role": "pose"},
    {"asset_id": "style", "sha256": "c" * 64, "title": "Style", "role": "style"},
]


async def settle(page):
    await page.evaluate(
        "()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))"
    )


async def mounted_page(context):
    page = await context.new_page()
    await page.set_content(HTML)
    await page.add_script_tag(path=str(SCRIPT))
    await page.wait_for_selector("#recipeShortlist")
    await page.evaluate(
        "sources => document.dispatchEvent(new CustomEvent('studio:shortlist-sources', {detail:sources}))",
        SOURCES,
    )
    return page


async def state(page):
    return await page.evaluate(
        """()=>({
          roles:[...document.querySelectorAll('#shortlistSourceList select')].map(x=>x.value),
          active:document.activeElement?.id,
          staleCards:document.querySelectorAll('#shortlistResults article').length,
          moveClicks:window.__moveClicks||0
        })"""
    )


async def run(out):
    from playwright.async_api import async_playwright

    checks = []

    def check(condition, label, detail=None):
        passed = bool(condition)
        checks.append({"label": label, "passed": passed, "detail": detail})
        print(("PASS " if passed else "FAIL ") + label, flush=True)
        assert passed, f"{label}: {detail}"

    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        executable = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium")
        browser = await playwright.chromium.launch(
            executable_path=executable or None,
            headless=True,
            args=["--no-sandbox"],
        )
        context = await browser.new_context()

        for key in ("Enter", "Space"):
            page = await mounted_page(context)
            await page.evaluate(
                """()=>{
                  window.__moveClicks=0;
                  const stale=document.createElement('article');
                  stale.textContent='stale report';
                  document.querySelector('#shortlistResults').append(stale);
                  document.addEventListener('click', event=>{
                    if(event.target.matches?.('[data-move]')){
                      window.__moveClicks++;
                      requestAnimationFrame(()=>document.querySelector('#checkStartingRecipes').focus());
                    }
                  }, true);
                }"""
            )
            target = page.locator('[data-slot="2"] [data-move="-1"]')
            old_button = await target.element_handle()
            # Deliberately mirrors the formerly flaky full-shell driver sequence.
            await target.focus()
            await page.keyboard.press(key)
            await settle(page)
            actual = await state(page)
            check(
                actual["roles"] == ["pose", "identity", "style"]
                and actual["active"] == "shortlistRole1"
                and actual["staleCards"] == 0,
                f"{key} reorders once, invalidates stale cards and restores focus",
                actual,
            )
            check(
                actual["moveClicks"] == 0,
                f"{key} does not depend on a deferred synthetic click",
                actual,
            )
            await old_button.evaluate("button => button.click()")
            await settle(page)
            actual = await state(page)
            check(
                actual["roles"] == ["pose", "identity", "style"]
                and actual["active"] == "shortlistRole1",
                f"{key} ignores a queued activation from the detached button",
                actual,
            )
            await page.close()

        page = await mounted_page(context)
        await page.evaluate(
            """()=>document.addEventListener('click', event=>{
              if(event.target.matches?.('[data-move]'))
                requestAnimationFrame(()=>document.querySelector('#checkStartingRecipes').focus());
            }, true)"""
        )
        await page.locator('[data-slot="2"] [data-move="-1"]').click()
        await settle(page)
        actual = await state(page)
        check(
            actual["roles"] == ["pose", "identity", "style"]
            and actual["active"] == "shortlistRole1",
            "pointer reorder restores focus after post-activation focus adjustment",
            actual,
        )
        await page.close()

        page = await mounted_page(context)
        await page.evaluate(
            """()=>{
              document.addEventListener('click', event=>{
                if(event.target.matches?.('[data-move]'))
                  requestAnimationFrame(()=>document.querySelector('#checkStartingRecipes').focus());
              }, true);
              document.querySelector('[data-slot="2"] [data-move="-1"]').click();
              document.querySelector('[data-slot="1"] [data-move="1"]').click();
            }"""
        )
        await settle(page)
        actual = await state(page)
        check(
            actual["roles"] == ["identity", "pose", "style"]
            and actual["active"] == "shortlistRole2",
            "only the latest render may restore focus",
            actual,
        )
        await page.close()

        await browser.close()

    receipt = {"checks": checks, "passed": sum(x["passed"] for x in checks)}
    (out / "result.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=ROOT / ".runtime" / "shortlist-keyboard-browser"
    )
    args = parser.parse_args()
    asyncio.run(run(args.out))
