"""Explicit Chromium proof for the bounded primary character-review bridge.

This driver uses the real Production/Workspace fixture and the shipped review
page against an ephemeral loopback HTTP listener.  It never touches the live
Studio or ComfyUI ports and is intentionally excluded from unittest discovery.

    python tests/character_review_browser.py --out <new evidence directory>
"""
import argparse
import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit

import test_character_study_results as collection_fixture
from test_server import server
import studio_use_cases


GENERATION_POST = re.compile(r"^/api/jobs$|^/api/[a-z0-9_/-]+/(?:start|resume|run|render|generate)$")
ROOT = Path(__file__).resolve().parents[1]


def _summary(path):
    return json.loads((Path(path) / "summary.json").read_text(encoding="utf-8"))


def run(out, chromium=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = collection_fixture.CollectionTests("runTest")
    fixture.setUp()
    http = worker = None
    posts = []
    errors = []
    dialogs = []
    try:
        # The inherited fixture gives us one completed 8x8 candidate, one used
        # reservation, and no running generation worker or real runtime.
        project = fixture.project()
        job = fixture.execute(project)
        identifier = project["id"]
        expected_sha = hashlib.sha256(collection_fixture.fixtures.PNG).hexdigest()
        baseline = {
            "jobs": copy.deepcopy(fixture.studio.jobs),
            "reserved": fixture.studio.production.get(identifier)["budget"]["reserved"],
            "requests": copy.deepcopy(fixture.studio.requests),
            "queue": fixture.studio.queue.qsize(),
        }
        assert job["status"] == "completed"
        assert len(job["outputs"]) == 1
        assert baseline["reserved"] == 1
        assert fixture.studio.production.get(identifier)["budget"]["allowance"] == 2

        Stub, _ = studio_use_cases.build_handler()

        class Handler(Stub, server.Handler):
            studio = fixture.studio

            def log_message(self, *args):
                pass

            def _safe_host(self):
                return self.headers.get("Host") == "127.0.0.1:" + str(self.server.server_port)

            def _safe_mutation(self):
                return self._safe_host() and self.headers.get("Origin") == "http://127.0.0.1:" + str(self.server.server_port)

            def do_GET(self):
                path = urlsplit(self.path).path
                # The review page, its JS/CSS, and every review artifact use the
                # production Handler's real static/file and review serializers.
                if path.startswith("/api/production") or path in {
                    "/review.html", "/review.js", "/review.css", "/static/studio.css",
                    "/static/studio-core.js", "/static/studio-shell.js",
                }:
                    return server.Handler.do_GET(self)
                return Stub.do_GET(self)

            def do_POST(self):
                path = urlsplit(self.path).path
                posts.append({"path": path, "body": None})
                # Any write other than the review route is forbidden.  The
                # generation deny-list is explicit so a future page regression
                # cannot silently start or resume model work in this proof.
                if GENERATION_POST.search(path):
                    return self._json(403, {"error": "Generation is forbidden in this fixture"})
                if path != "/api/production/" + identifier + "/review":
                    return self._json(403, {"error": "Only the review route is allowed in this fixture"})
                size = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(size)
                try:
                    posts[-1]["body"] = json.loads(raw)
                except (TypeError, ValueError):
                    posts[-1]["body"] = None
                # Reconstruct a body for Handler._body_json without changing the
                # actual request semantics or bypassing its Origin/Host checks.
                from io import BytesIO
                self.rfile = BytesIO(raw)
                self.headers["Content-Length"] = str(len(raw))
                return server.Handler.do_POST(self)

        # CollectionTests patches Thread.start to keep its worker stopped.  Stop
        # only that first owned patch before starting the HTTP listener.
        fixture.patches[0].stop()
        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        origin = "http://127.0.0.1:" + str(http.server_port)

        with __import__("playwright.sync_api", fromlist=["sync_playwright"]).sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=chromium or os.environ.get("CHROMIUM_PATH") or shutil.which("chromium") or None,
                args=["--no-sandbox", "--disable-gpu"],
            )
            browser_version = browser.version
            context = browser.new_context(viewport={"width": 1440, "height": 980}, reduced_motion="reduce")
            page = context.new_page()
            page.set_default_timeout(9000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
            page.goto(origin + "/review.html?project=" + identifier, wait_until="networkidle")
            page.locator("#open").wait_for(state="visible")
            assert not fixture.studio.production.reviews.exists(identifier)

            page.locator("#open").click()
            page.locator("#phase").filter(has_text="Blind review").wait_for()
            page.locator("#characterAssessment").wait_for(state="visible")
            page.locator("#characterChecks").wait_for(state="visible")
            required = page.locator("#characterChecks select")
            assert required.count() == 1, "fixture case must expose its one exact required character check"
            character_checks = {}
            for index in range(required.count()):
                control = required.nth(index)
                check_id = control.get_attribute("data-check-id") or control.get_attribute("name") or control.get_attribute("id", )
                assert check_id, "character check select must identify its exact check"
                check_id = re.sub(r"^character-check-", "", check_id)
                # Keyboard selection is deliberate: each exact check must be
                # set to pass before the assessment is submitted.
                control.focus()
                control.press("p")
                assert control.input_value() == "pass"
                character_checks[check_id] = "pass"

            page.locator("#verdict").select_option("keep")
            page.locator("#check-constraints").select_option("pass")
            page.locator("#notes").fill("Explicit character review fixture; exact required check passed.")
            page.locator("#saveAssessment").focus()
            page.locator("#saveAssessment").press("Enter")
            page.locator("#assessmentStatus").filter(has_text="Saved").wait_for()
            rate_payload = posts[-1]["body"]
            assert rate_payload["action"] == "rate"
            assert rate_payload.get("reviewer", "local-user") == "local-user"
            assert rate_payload["assessment"]["character_checks"] == character_checks

            page.locator("#reveal").click()
            page.locator("#phase").filter(has_text="Settings revealed").wait_for()
            assert dialogs and "Reveal" in dialogs[-1]
            page.locator("#characterDecision").wait_for(state="visible")
            page.locator("#selected").select_option("A")
            page.locator("#characterDecision").select_option("accepted")
            page.locator("#summary").fill("The exact required character check passes; accept this retained output.")
            page.locator("#finalize").click()
            page.locator("#phase").filter(has_text="Decision recorded").wait_for()
            page.locator("#characterDecisionStatus").filter(has_text="accepted").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow at 1440px"
            final_payload = posts[-1]["body"]
            assert final_payload["action"] == "finalize"
            assert final_payload["selected"] == "A"
            assert final_payload["character_decision"] == "accepted"
            assert final_payload.get("reviewer", "local-user") == "local-user"
            accepted_saved = fixture.studio.production.reviews.inspect(identifier)
            assert accepted_saved["finalized"] is True
            assert accepted_saved["candidates"][0]["character_checks"] == character_checks
            context = accepted_saved["character_context"]
            assert context["schema_version"] == 1
            assert context["plan_sha256"] == fixture.plan["plan_sha256"]
            assert context["case_id"] == fixture.plan["cases"][0]["id"]
            assert set(context["required_checks"]) == set(character_checks)
            accepted_history_length = len(accepted_saved["history"])
            assert accepted_saved["character_review"]["review"]["decision"] == "accepted"
            assert accepted_saved["character_review"]["review"]["reviewer"] == "local-user"

            # An agent may record a selection, but cannot claim human
            # acceptance.  This request must leave the accepted receipt intact.
            connection = HTTPConnection("127.0.0.1", http.server_port, timeout=10)
            try:
                agent_payload = {
                    "action": "finalize", "expected_revision": accepted_saved["revision"], "selected": "A",
                    "notes": "Agent must not accept.", "character_decision": "accepted", "reviewer": "local-agent",
                }
                connection.request("POST", "/api/production/" + identifier + "/review", json.dumps(agent_payload),
                                   {"Host": "127.0.0.1:" + str(http.server_port), "Origin": origin,
                                    "Content-Type": "application/json"})
                response = connection.getresponse()
                assert response.status == 400
                response.read()
            finally:
                connection.close()
            assert fixture.studio.production.reviews.inspect(identifier)["character_review"]["review"]["decision"] == "accepted"

            # Collection is an independent durable-receipt check while the
            # accepted revision is current.  The mobile pass below then edits
            # that same review and proves a fresh collection becomes unaccepted.
            first_destination = fixture.workspace / "collected-browser-v1"
            fixture.destination = first_destination
            fixture.collect()
            first_summary = _summary(first_destination)
            first_records = json.loads((first_destination / "records.json").read_text(encoding="utf-8"))
            assert first_summary["human_accepted_cases"] == 1
            assert len(first_records) == 1
            assert first_records[0]["review"]["decision"] == "accepted"
            assert first_records[0]["review"]["reviewer"] == "local-user"
            assert first_records[0]["review"]["output_sha256"] == expected_sha
            assert first_records[0]["output"]["sha256"] == expected_sha
            page.screenshot(path=str(out / "review-desktop-1440.png"), full_page=True)

            # The same saved review is reopened at 390px.  A changed assessment
            # must clear current acceptance while retaining the finalize event.
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="networkidle")
            page.locator("#desk").wait_for(state="visible")
            page.wait_for_function("document.querySelector('#characterDecisionStatus').textContent.toLowerCase().includes('accepted')")
            assert all(page.locator("#characterChecks select").nth(index).input_value() == "pass"
                       for index in range(page.locator("#characterChecks select").count()))
            page.locator("#notes").fill("Changed assessment: retain the original event, clear acceptance.")
            page.locator("#saveAssessment").focus()
            page.locator("#saveAssessment").press("Enter")
            page.locator("#assessmentStatus").filter(has_text="Saved").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow at 390px"
            page.screenshot(path=str(out / "review-mobile-390.png"), full_page=True)

            assert not errors, errors
            context.close()
            browser.close()

        saved = fixture.studio.production.reviews.inspect(identifier)
        assert saved["finalized"] is False
        assert saved.get("character_review") is None
        assert any(event["action"] == "finalize" for event in saved["history"])
        assert len(saved["history"]) > accepted_history_length
        assert all(event["action"] != "finalize" or event.get("reviewer") == "local-user" for event in saved["history"])

        # A second read-only collection after the changed assessment is the
        # required zero-count case.
        second_destination = fixture.workspace / "collected-browser-v2"
        fixture.destination = second_destination
        fixture.collect()
        second_summary = _summary(second_destination)
        assert second_summary["human_accepted_cases"] == 0
        assert first_summary["human_accepted_cases"] == 1
        assert first_records and first_records[0]["output"]["sha256"] == expected_sha

        # The accepted receipt is retained in the review history even though the
        # current revision is no longer accepted.  Require its output binding and
        # local-user actor from the durable current document/history where present.
        accepted_events = [event for event in saved["history"] if event["action"] == "finalize"]
        assert accepted_events and all(event.get("reviewer") == "local-user" for event in accepted_events)
        assert fixture.studio.production.get(identifier)["budget"] == {"allowance": 2, "reserved": 1}
        assert len(fixture.studio.jobs) == len(baseline["jobs"])
        assert fixture.studio.requests == baseline["requests"]
        assert fixture.studio.queue.qsize() == baseline["queue"]
        assert not any(GENERATION_POST.search(post["path"]) for post in posts)

        result = {
            "scope": "Synthetic completed primary character case, real Chromium, real Handler, no model runtime",
            "project_id": identifier,
            "browser": browser_version,
            "viewports": [1440, 390],
            "page_errors": errors,
            "dialogs": dialogs,
            "review_posts": [post for post in posts if post["path"].endswith("/review")],
            "generation_posts": [post for post in posts if GENERATION_POST.search(post["path"])],
            "baseline": {"reserved": baseline["reserved"], "request_count": len(baseline["requests"]), "queue": baseline["queue"]},
            "after": {"reserved": fixture.studio.production.get(identifier)["budget"]["reserved"],
                      "request_count": len(fixture.studio.requests), "queue": fixture.studio.queue.qsize()},
            "output_sha256": expected_sha,
            "collection_v1": {"human_accepted_cases": first_summary["human_accepted_cases"], "output_sha256": first_records[0]["output"]["sha256"]},
            "collection_v2": {"human_accepted_cases": second_summary["human_accepted_cases"]},
            "checks": ["keyboard exact-check save", "explicit reveal dialog", "local-user accepted decision payload",
                        "390px no horizontal overflow", "changed assessment clears acceptance", "collector hash binding",
                        "no generation/start/resume POST", "no jobs/reservations/runtime request increase"],
        }
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (out / "collection-v1-summary.json").write_text(json.dumps(first_summary, indent=2) + "\n", encoding="utf-8")
        (out / "collection-v2-summary.json").write_text(json.dumps(second_summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"out": str(out), "collection_v1_human_accepted": first_summary["human_accepted_cases"],
                          "collection_v2_human_accepted": second_summary["human_accepted_cases"], "output_sha256": expected_sha}))
    finally:
        if http:
            http.shutdown()
            http.server_close()
        if worker:
            worker.join(5)
        fixture.doCleanups()
    assert worker is None or not worker.is_alive()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chromium")
    args = parser.parse_args()
    run(args.out, args.chromium)
