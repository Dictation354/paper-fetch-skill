"""Provider-owned supplementary panel activation."""


def reveal_supplement(page, link, visible_link, remaining_ms):
    if link.is_visible():
        return
    tab = page.locator("a[href='#supplementary_data']:visible").first
    if not tab.count():
        hidden_tab = page.locator("a[href='#supplementary_data']").first
        menu = hidden_tab.locator(
            "xpath=ancestor::li[contains(concat(' ', normalize-space(@class), ' '), ' dropdown ')][1]"
        )
        menu.locator("[data-toggle='dropdown']").first.click(timeout=remaining_ms())
    tab.click(timeout=remaining_ms())
    visible_link.wait_for(state="visible", timeout=remaining_ms())
