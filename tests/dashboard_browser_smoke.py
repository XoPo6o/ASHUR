from pathlib import Path

from playwright.sync_api import sync_playwright


HTML = Path(__file__).resolve().parents[1] / "wall-preview.html"


def main():
    page_errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(HTML.as_uri(), wait_until="domcontentloaded")

        for width, height in ((1440, 900), (768, 1024), (390, 844), (360, 800)):
            page.set_viewport_size({"width": width, "height": height})
            result = page.evaluate("""() => {
                const nav = document.querySelector('.nav');
                const links = [...document.querySelectorAll('.nav a')];
                const chart = document.querySelector('#daily-pnl-chart');
                return {
                    viewport: window.innerWidth,
                    document: document.documentElement.scrollWidth,
                    navOverflow: getComputedStyle(nav).overflowX,
                    minNavLinkHeight: Math.min(...links.map(link => link.getBoundingClientRect().height)),
                    chartWidth: chart.getBoundingClientRect().width
                };
            }""")
            if result["document"] > result["viewport"]:
                raise AssertionError(
                    f"Horizontal page overflow at {width}px: {result['document']}px"
                )
            if result["chartWidth"] <= 0:
                raise AssertionError(f"Chart is not visible at {width}px")
            if width <= 620:
                if result["navOverflow"] not in ("auto", "scroll"):
                    raise AssertionError("Mobile navigation is not horizontally scrollable")
                if result["minNavLinkHeight"] < 44:
                    raise AssertionError("Mobile navigation targets are smaller than 44px")

        browser.close()

    if page_errors:
        raise AssertionError("Browser JavaScript errors: " + " | ".join(page_errors))


if __name__ == "__main__":
    main()
