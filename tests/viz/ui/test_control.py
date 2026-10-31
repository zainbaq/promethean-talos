"""The control room in the page: hidden without leave to write; cards, chat and preset post the right requests."""
from __future__ import annotations

import json

from .conftest import PHONE

CONTROL = {"preset": "medium", "presets": [{"name": "lite", "usd_per_item": None}, {"name": "medium", "usd_per_item": 8.5}, {"name": "heavy", "usd_per_item": None}],
           "messages": [{"id": "MSG-0001", "ts": "2026-10-28T10:00:00Z", "kind": "message", "text": "<b>keep it warm</b>", "ack": None}],
           "runner": {"active": False, "doing": None, "phase": None}}


def stub(authed=True):
    """An init script that fakes the session and the snapshot's control block, and records every POST."""
    return """
    window.__posts = [];
    const real = window.fetch;
    window.fetch = async (url, opts) => {
      if (String(url) === '/api/session') return new Response(JSON.stringify({writable: true, authed: %s}));
      if (String(url).startsWith('/api/control/')) { window.__posts.push([String(url), JSON.parse(opts.body)]); return new Response('{"ok":true}'); }
      const res = await real(url, opts);
      if (String(url).includes('sample-company.json') && !String(url).includes('hierarchy')) {
        const data = await res.json(); data.control = %s;
        data.waiting.push({kind: 'question', key: 'Q-0009', id: 'Q-0009', title: 'Which one?'});
        return new Response(JSON.stringify(data));
      }
      return res;
    };""" % ("true" if authed else "false", json.dumps(CONTROL))


Q = "view=now&data=sample-company&motion=reduce"


def test_hidden_without_a_control_block(open_page):
    page = open_page(Q)
    assert page.locator(".chat").is_hidden() and page.locator(".dock").is_hidden() and page.locator(".top__preset").is_hidden()
    assert page.locator(".waits").is_visible()


def test_a_page_without_the_link_stays_view_only(open_page):
    page = open_page(Q, init_script=stub(authed=False))
    page.wait_for_timeout(300)
    assert page.locator(".chat").is_hidden() and page.locator(".dock").is_hidden()


def test_cards_chat_and_preset_post(open_page):
    page = open_page(Q, init_script=stub(), wait=".chat__input")
    posts = lambda: page.evaluate("window.__posts")  # noqa: E731
    gate = page.locator('.ctlcard[data-kind="gate"]').first
    gate.locator(".btn--go").click()
    assert posts() == []  # the first tap only arms it
    gate.locator(".btn--go").click()
    assert posts()[-1][0] == "/api/control/approve" and "gate" in posts()[-1][1]
    question = page.locator('.ctlcard[data-kind="question"]').first
    question.locator("input").fill("yes")
    question.locator("button").click()
    assert posts()[-1][0] == "/api/control/answer" and posts()[-1][1]["text"] == "yes"
    page.fill(".chat__input", "hello")
    page.click(".chat__send")
    page.wait_for_function("document.querySelector('.chat__input').value === ''")
    assert posts()[-1] == ["/api/control/say", {"text": "hello"}]
    page.locator('.top__preset [data-preset="heavy"]').click()
    assert posts()[-1] == ["/api/control/preset", {"name": "heavy"}]
    page.click(".chat__toggle")
    assert page.locator(".msg--you .msg__text").first.inner_text() == "<b>keep it warm</b>"  # text, never markup
    assert page.locator(".msg__ack.is-pending").count() == 1


def test_phone_cards_fit(open_page):
    page = open_page(Q, init_script=stub(), wait=".chat__input", size=PHONE)
    assert page.evaluate("document.documentElement.scrollWidth") <= PHONE["width"]
    box = page.locator(".ctlcard__kind").first.bounding_box()
    assert box["height"] < 30  # the label stays on one line
