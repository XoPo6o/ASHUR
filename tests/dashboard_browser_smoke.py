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
                    chartWidth: chart.getBoundingClientRect().width,
                    overflowers: [...document.querySelectorAll("body *")]
                        .map(element => ({tag: element.tagName, id: element.id, className: String(element.className || "").slice(0, 100),
                            left: Math.round(element.getBoundingClientRect().left),
                            right: Math.round(element.getBoundingClientRect().right),
                            width: Math.round(element.getBoundingClientRect().width)}))
                        .filter(item => item.right > window.innerWidth + 1 || item.left < -1)
                        .slice(0, 12)
                };
            }""")
            if result["document"] > result["viewport"]:
                raise AssertionError(
                    f"Horizontal page overflow at {width}px: {result['document']}px; elements={result['overflowers']}"
                )
            if result["chartWidth"] <= 0:
                raise AssertionError(f"Chart is not visible at {width}px")
            if width <= 620:
                if result["navOverflow"] not in ("auto", "scroll"):
                    raise AssertionError("Mobile navigation is not horizontally scrollable")
                if result["minNavLinkHeight"] < 44:
                    raise AssertionError("Mobile navigation targets are smaller than 44px")

        page.set_viewport_size({"width": 390, "height": 844})
        accessibility = page.evaluate("""() => ({
            header: Boolean(document.querySelector('header')),
            main: Boolean(document.querySelector('main')),
            footer: Boolean(document.querySelector('footer')),
            labelledNavigation: Boolean(document.querySelector('nav[aria-label]')),
            headingCount: document.querySelectorAll('h1').length,
            labelledCharts: [...document.querySelectorAll('svg.chart')].every(
                chart => chart.getAttribute('role') === 'img' && Boolean(chart.getAttribute('aria-label'))
            ),
            liveStatus: Boolean(document.querySelector('[role="status"][aria-live="polite"]'))
        })""")
        if not all(accessibility.values()):
            raise AssertionError(f"Accessibility baseline failed: {accessibility}")

        page.keyboard.press("Tab")
        focus_style = page.evaluate("""() => {
            const style = getComputedStyle(document.activeElement);
            return {outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth};
        }""")
        if focus_style["outlineStyle"] == "none" or focus_style["outlineWidth"] == "0px":
            raise AssertionError("Keyboard focus indicator is not visible")

        page.emulate_media(reduced_motion="reduce")
        if page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") != "auto":
            raise AssertionError("Reduced-motion preference is not respected")

        browser.close()

    if page_errors:
        raise AssertionError("Browser JavaScript errors: " + " | ".join(page_errors))


if __name__ == "__main__":
    main()
