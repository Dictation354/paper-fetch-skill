"""Provider-owned supplementary panel activation."""


def reveal_supplement(page, link, visible_link, remaining_ms):
    if link.is_visible():
        return
    modal = link.locator("xpath=ancestor::*[@id='supplementaryModal']")
    if modal.count():
        controls = page.locator("[data-reveal-id='supplementaryModal']")
        for index in range(controls.count()):
            if controls.nth(index).is_visible():
                controls.nth(index).click(timeout=remaining_ms())
                break
        visible_link.wait_for(state="visible", timeout=remaining_ms())
