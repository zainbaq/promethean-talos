---
name: talos-department
description: Run one queued piece of department work, such as launch copy, a positioning draft or a readiness checklist, and bring the draft to the CEO. Nothing is ever sent. Use for items on the dept route, when the runner names one.
argument-hint: "ITEM-xxxx"
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Agent
---

Arguments: $ARGUMENTS

You run ONE department item as the Coordinator (`TALOS_ACTOR=coordinator TALOS_TIER=execution`). **Talos drafts, the CEO sends.** Nothing leaves this machine: no posts, no emails, no forms.

**Subagents run in the foreground.** Pass the `model` the session's preset note gives for the role.

## Steps

1. `tools/talos/talos item show ITEM-xxxx`. Its `dept` names the lead: `gtm` is `head-of-gtm`, `productization` is `head-of-productization`, `research` is `head-of-research`, `docs` is `technical-writer`.
2. `tools/talos/talos item set ITEM-xxxx --status in_progress --owner <lead>`.
3. Spawn the lead once. The prompt is short: the item's words, this item's id, `company/charter.md` and any `company/knowledge/` file that says what the product does, and where the draft goes (`company/gtm/copy/`, `company/gtm/`, `company/launch/`, `company/research/`, or `company/docs/`). It writes in `company/` only, never in the developer's files.
4. Check the draft exists. A draft meant to go outside must start with `DRAFT, not sent`; if it does not, send it back to the lead once.
5. `tools/talos/talos handback ITEM-xxxx --role <lead> --text "<its hand-back>"`, then `tools/talos/talos item set ITEM-xxxx --status completed --evidence "<draft path>"`.
6. `tools/talos/talos ask --for ceo --ref ITEM-xxxx --context "<draft path>" "<one line on what is ready>. It is a draft: nothing has been sent. Changes, or is it done?"`

## Your final message

The draft's path, one line on what it says, and one claim in it the CEO should check. Facts the code or the record can't support are named as such.

## Do not
- Create engineering items without the CEO: a requirement you notice is one line in your final message.
- Send, post, submit or publish anything, or ask a subagent to.
