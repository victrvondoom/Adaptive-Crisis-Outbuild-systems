"""Phase VI: real-browser verification of the advanced System Design Studio."""
import os

import pytest

from .test_journeys import server, _login, VIEWPORTS  # noqa: F401  (fixtures reused)

pytestmark = pytest.mark.browser
SHOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "phase-6", "screenshots"))



def test_advanced_studio_journey(server, browser):
    os.makedirs(SHOT, exist_ok=True)
    page = browser.new_page(viewport=VIEWPORTS["desktop"])
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # console 'Failed to load resource' lines omit the URL, so track failing responses directly.
    # /favicon.ico 404 is pre-existing (no favicon shipped) and ignored; 429 is the expected rate limiter.
    page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400
            and not r.url.endswith("/favicon.ico") and r.status != 429 else None)
    _login(page, server, "ngo-admin@example.dev")
    page.click("button[data-tab='studio']")
    page.wait_for_selector("#sdTopicList .sd-topic-card")
    assert page.locator("#sdTopicList .sd-topic-card").count() == 20            # foundations preserved
    page.click("#sdTrackAdvanced")
    page.wait_for_function("document.querySelectorAll('#sdTopicList .sd-topic-card').length === 20")
    assert page.locator("#sdAdvBanner").is_visible()
    assert "21 ·" in page.locator("#sdTopicList").inner_text() and "40 ·" in page.locator("#sdTopicList").inner_text()
    page.click("text=28 · Distributed Locks")
    detail = page.locator("#sdTopicDetail").inner_text().upper()
    for needle in ("PLAIN-ENGLISH DEFINITION", "ARCHITECTURE DIAGRAM", "DATA FLOW", "SOURCE REFERENCES", "FAILURE SCENARIO",
                   "SECURITY IMPLICATIONS", "BENCHMARK METHODOLOGY", "KNOWLEDGE CHECK", "FENCING"):
        assert needle in detail, needle
    # real lab through the real API
    page.click("text=▶ Run lab: lease")
    page.wait_for_selector("#advLabOut .sd-inv", timeout=30000)
    out = page.locator("#advLabOut").inner_text()
    assert "REAL MEASURED" in out and "stale holder rejected" in out and "✗" not in out
    # quiz: a wrong answer explains itself, a right one is marked
    page.click("#advQuiz .sd-quiz >> nth=0 >> .sd-opt >> nth=1")
    assert "Correct" in page.locator("#advQuiz").inner_text()
    page.click("#advQuiz .sd-quiz >> nth=1 >> .sd-opt >> nth=1")
    assert "Not quite" in page.locator("#advQuiz").inner_text()
    page.screenshot(path=os.path.join(SHOT, "advanced_topic_desktop.png"))
    # simulated labs are labelled as such
    page.click("button[onclick=\"advSelectChapter(0)\"]")
    page.click("text=🧪 Failure Lab")
    page.click("text=Network partition (simulated)")
    page.wait_for_selector("#sdLabResult .status-chip")
    assert "SIMULATED" in page.locator("#sdLabResult").inner_text()
    # architecture explorer: advanced component with all required fields; secrets not shown
    page.click("text=🗺️ Architecture Map")
    page.click("#sdMapGrid >> text=Object storage")
    d = page.locator("#sdMapDetail").inner_text()
    for needle in ("Responsibility", "Source path", "Configuration", "Security boundary", "Failure mode", "Decision record"):
        assert needle in d, needle
    page.click("#sdMapGrid >> text=Secret manager / KMS")
    assert "BLOCKED" in page.locator("#sdMapDetail").inner_text()
    # production engineering: real telemetry (after some traffic) and NOT MEASURED honesty
    page.click("text=🏭 Production Engineering")
    page.click("text=Load live telemetry")
    page.wait_for_selector("#sdProdLive .atlas-feature")
    prod = page.locator("#sdProdLive").inner_text()
    assert "REAL TELEMETRY" in prod
    assert "queue lag" in prod.lower() and "CANDIDATE OBJECTIVE" in prod
    page.screenshot(path=os.path.join(SHOT, "production_engineering_desktop.png"))
    # foundations still reachable
    page.click("text=📚 Topics")
    page.click("#sdTrackFoundations")
    assert page.locator("#sdTopicList .sd-topic-card").count() == 20
    assert not errors, errors
    page.close()


def test_advanced_studio_mobile_no_horizontal_overflow(server, browser):
    page = browser.new_page(viewport=VIEWPORTS["mobile"])
    _login(page, server, "ngo-admin@example.dev")
    page.click("button[data-tab='studio']")
    page.click("#sdTrackAdvanced")
    page.wait_for_selector("#sdTopicList .sd-topic-card")
    page.click("text=22 · Indexing")
    page.wait_for_selector("#sdTopicDetail .sd-flow")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"horizontal overflow {overflow}px"
    page.screenshot(path=os.path.join(SHOT, "advanced_topic_mobile.png"), full_page=False)
    page.close()
