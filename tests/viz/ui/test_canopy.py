"""Canopy: the tree, the Follow and Relay lenses, the scrubber, cards. Fixture: hierarchy-sample-company.json."""
from __future__ import annotations

Q = "view=canopy&data=sample-company&motion=reduce"


def test_tree_draws_every_task_with_its_outcome(open_page):
    page = open_page(Q, wait=".leaf[data-task]")
    assert page.locator(".leaf[data-task]").count() == 9
    for cls, n in (("verified", 1), ("sent_back", 1), ("blocked", 1), ("abandoned", 1), ("support", 5)):
        assert page.locator(f".leaf.leaf--{cls}[data-task]").count() == n
    assert page.locator(".tree-tip").count() == 3
    assert page.locator(".canopy__stats b").first.inner_text() == "$41"
    assert page.errors == []


def test_follow_shows_the_route_and_the_wait_on_you(open_page):
    page = open_page(f"{Q}&lens=follow&item=ITEM-0001", wait=".tree-route")
    assert "waited 1h14m for you" in page.locator(".tree-attn").all_text_contents()
    assert page.locator(".relay__wait").count() == 1
    assert page.locator(".relay__gap").count() == 4
    assert page.locator(".tree-ring").count() == 3


def test_relay_has_one_lane_per_role(open_page):
    page = open_page(f"{Q}&lens=relay&item=ITEM-0001", wait=".baton-stop")
    assert page.locator(".lane").count() == 6
    assert page.locator(".baton-stop").count() == 7
    assert page.locator(".canopy__scrub").is_hidden()


def test_scrubber_hides_what_had_not_happened_yet(open_page):
    page = open_page(Q, wait=".leaf[data-task]")
    page.locator(".canopy__range").evaluate("e => { e.value = 0; e.dispatchEvent(new Event('input')); }")
    assert page.locator(".leaf[data-task]:visible").count() == 0
    assert page.locator(".canopy__time").inner_text() != "now"
    page.locator(".canopy__range").evaluate("e => { e.value = 1000; e.dispatchEvent(new Event('input')); }")
    assert page.locator(".leaf[data-task]:visible").count() == 9


def test_tapping_a_leaf_pins_its_card_and_escape_clears_it(open_page):
    page = open_page(Q, wait=".leaf[data-task]")
    page.locator('.leaf[data-task="agent-4"]').dispatch_event("click")
    assert page.locator(".canopy__card h2").inner_text() == "Apply review fixes ITEM-0001"
    page.get_by_role("link", name="Follow ITEM-0001").click()
    page.wait_for_selector(".tree-route")
    assert "lens=follow" in page.url and "item=ITEM-0001" in page.url
    page.get_by_role("button", name="Tree").click()
    page.locator('.leaf[data-task="agent-4"]').dispatch_event("click")
    page.keyboard.press("Escape")
    assert page.locator(".canopy__kicker").first.inner_text().lower() == "the whole company"


def test_unreadable_hierarchy_says_so(open_page):
    page = open_page("view=canopy&data=empty&motion=reduce", wait=".canopy__empty:not([hidden])")
    assert page.locator(".canopy__empty").inner_text() == "The hierarchy could not be read."
