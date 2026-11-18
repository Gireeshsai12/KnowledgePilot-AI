"""Local Playwright smoke test against a running server."""
import argparse
import uuid

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--chromium-path")
args = parser.parse_args()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium_path)
    page = browser.new_page(viewport={"width": 1240, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url)
    page.get_by_label("Email", exact=True).fill(f"browser-{uuid.uuid4().hex}@example.test")
    page.get_by_label("Password", exact=True).fill(uuid.uuid4().hex)
    page.get_by_role("button", name="Create account").click()
    page.get_by_role("button", name="Load samples").click()
    expect(page.get_by_role("status")).to_contain_text("3 sample documents indexed.")
    page.get_by_label("Question or keywords").fill("How many vacation days do employees receive?")
    page.get_by_role("button", name="Ask a question").click()
    expect(page.locator("#results")).to_contain_text("20 vacation days")
    page.locator("#results").get_by_role("button", name="Vacation days").first.click()
    expect(page.get_by_role("dialog")).to_contain_text("20 vacation days")
    page.get_by_role("button", name="Close source").click()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth === innerWidth"), "Horizontal overflow"
    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()
    assert not errors, errors
    browser.close()
print("Chromium smoke passed: account, samples, question, source, mobile layout and sign-out.")
