#!/usr/bin/env python3
"""Native browser proof for accessible setup compatibility selector states."""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import shutil

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]


def report() -> dict:
    authority = {
        "provider_accessed": False,
        "file_hashed": False,
        "model_downloaded": False,
        "installation_authorized": False,
        "backend_switched": False,
        "selection_changed": False,
        "generation_submitted": False,
    }
    rows = []
    specs = [
        ("alpha", "Alpha", "recommended"),
        ("beta", "Beta", "possible"),
        ("gamma", "Gamma", "needs_review"),
        ("delta", "Delta <img id=unsafe src=x>", "incompatible"),
    ]
    for candidate_id, name, status in specs:
        rows.append({
            "id": candidate_id,
            "name": name,
            "identity": "sha256:" + candidate_id[0] * 64,
            "status": status,
            "selectable": status in {"recommended", "possible"},
            "expert_override_required": status == "needs_review",
            "recommendation_rank": 1 if status == "recommended" else None,
            "hard_conflicts": [{"code": "architecture_mismatch", "message": "Architecture does not match."}] if status == "incompatible" else [],
            "unknowns": [{"code": "local_file_unverified", "message": "Exact local bytes need review."}] if status == "needs_review" else [],
            "limitations": [{"code": "weak_evidence", "message": "Evidence does not justify a recommendation."}] if status == "possible" else [],
            "evidence_summary": {"strong_support": 0, "strong_contradiction": 0, "qualifying_gallery_sources": 0, "qualifying_gallery_observations": 0, "weaker_support": 0},
        })
    return {
        "format": "studio.setup-context-compatibility-report/v1",
        "context_sha256": "a" * 64,
        "precondition": {"inventory_revision": "b" * 64, "schema_revision": "c" * 64, "backend_id": "primary", "runtime": "comfyui", "switching": False},
        "compatibility_input": {
            "format": "studio.setup-compatibility-input/v1",
            "slot": {"role": "lora"},
            "candidates": [{"id": row["id"], "name": row["name"], "identity": row["identity"]} for row in rows],
            "evidence": [],
        },
        "compatibility": {"format": "studio.setup-compatibility-report/v1", "context_sha256": "d" * 64, "candidates": rows, "diagnostics": [], **authority},
        "source_contexts": [],
        "observations": [],
        "diagnostics": [],
        "notice": "Advice only.",
        **authority,
    }


async def run(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH") or shutil.which("chromium") or None,
            headless=True,
            args=["--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        await page.set_content(
            """<!doctype html><html><head><meta charset='utf-8'></head><body>
            <main><label for='candidate'>Adapter</label>
            <select id='candidate'>
              <option value='alpha'>Alpha</option><option value='beta' selected>Beta</option>
              <option value='gamma'>Gamma</option><option value='delta'>Delta</option>
              <option value='extra'>Unreviewed extra</option>
            </select><div id='compatibility'></div></main>
            <script>window.selectionEvents=0;candidate.addEventListener('change',()=>selectionEvents++);</script>
            </body></html>"""
        )
        await page.add_style_tag(content=(ROOT / "app/static/setup-compatibility-selector.css").read_text(encoding="utf-8"))
        await page.add_script_tag(content=(ROOT / "app/static/setup-compatibility-selector.js").read_text(encoding="utf-8"))
        await page.evaluate(
            "([report])=>{window.presenter=StudioSetupCompatibilitySelector.mount(candidate,report,{container:compatibility,label:'Adapter compatibility'});}",
            [report()],
        )

        assert await page.locator("#candidate").get_attribute("aria-describedby")
        assert await page.locator("[data-compatibility-status]").get_attribute("role") == "status"
        assert "Possible" in await page.locator("[data-compatibility-status]").inner_text()
        assert await page.locator("option[value=gamma]").is_disabled()
        assert await page.locator("option[value=delta]").is_disabled()
        assert await page.locator("option[value=extra]").is_disabled()
        assert await page.evaluate("selectionEvents") == 0
        assert await page.locator("#unsafe").count() == 0
        assert "<img" in await page.locator("option[value=delta]").inner_text()

        expert = page.get_by_role("checkbox", name="Show Needs review choices for expert review")
        await expert.focus()
        await page.keyboard.press("Space")
        assert await expert.is_checked()
        assert not await page.locator("option[value=gamma]").is_disabled()
        assert await page.locator("option[value=delta]").is_disabled()
        assert await page.locator("option[value=extra]").is_disabled()
        assert await page.evaluate("selectionEvents") == 0

        await page.select_option("#candidate", "gamma")
        assert await page.evaluate("selectionEvents") == 1
        assert "Needs review" in await page.locator("[data-compatibility-status]").inner_text()

        await page.evaluate("document.documentElement.style.zoom='2'")
        overflow = await page.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
        assert overflow <= 1, f"selector presenter overflowed by {overflow}px at 390px / 200% zoom"
        await page.screenshot(path=out / "selector-390-zoom-200.png", full_page=True)

        await page.evaluate("presenter.destroy()")
        assert await page.locator("[data-setup-compatibility]").count() == 0
        assert await page.locator("option[value=delta]").inner_text() == "Delta"
        assert not await page.locator("option[value=delta]").is_disabled()
        assert errors == [], errors
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / ".runtime/setup-compatibility-selector")
    args = parser.parse_args()
    asyncio.run(run(args.out))
