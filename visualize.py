#!/usr/bin/env python3
"""
Render the chat data as browsable conversations, with each ad opportunity
shown in place as a slot placeholder.

Usage:
    python visualize.py                          # the known opportunities
    python visualize.py --match out.csv          # ...with the offer you served in each slot
    python visualize.py --discover out.csv       # ...diffed against the ones you found
    python visualize.py --match m.csv --discover d.csv --open

An opportunity records the conversation as it looked when the ad request
fired, so its `assistant_message_count` of k means "after the k-th assistant
message". That is where the placeholder is drawn. A long conversation can
therefore hold several opportunities.

With --discover, every slot is labelled by how your output compares to the
known opportunities: matched, missed, or new.
"""

import argparse
import csv
import html
import json
import os
import webbrowser
from collections import defaultdict

from validate import load_offers, open_data, norm

csv.field_size_limit(10**9)


def load(name):
    with open_data(name) as f:
        return list(csv.DictReader(f))


def load_rows(path, columns):
    """Read a candidate output CSV, checking it has the columns we need."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in columns if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Error: {path} is missing column(s): {', '.join(missing)}")
        return list(reader)


def build_chats(match_path=None, discover_path=None):
    """Group messages into chats and hang every ad slot off the right message."""
    chats = defaultdict(lambda: {"messages": [], "markers": defaultdict(list), "meta": {}})

    for m in load("chat-data.csv"):
        key = (m["visitor_id"], m["session_id"], str(m["chat_id"]))
        chats[key]["messages"].append(m)
    for chat in chats.values():
        chat["messages"].sort(key=lambda m: m["created_at"])

    # Part 1: slot_id -> offer_id
    served = {}
    offers = {}
    if match_path:
        offers = load_offers()
        for row in load_rows(match_path, ["ad_slot_id", "offer_id"]):
            offer_id = (row.get("offer_id") or "").strip()
            served[row["ad_slot_id"].strip()] = offer_id

    # Part 2: the opportunities the candidate found
    discovered = set()
    if discover_path:
        cols = ["visitor_id", "session_id", "chat_id", "assistant_message_count"]
        for row in load_rows(discover_path, cols):
            discovered.add(tuple(norm(row[c]) for c in cols))

    baseline = set()
    for o in load("ad-opportunities.csv"):
        slot = json.loads(o["slot_data"])
        key = (o["visitor_id"], o["session_id"], str(slot.get("chat_id", "")))
        after = int(slot["assistant_message_count"])
        ident = (norm(key[0]), norm(key[1]), norm(key[2]), norm(after))
        baseline.add(ident)

        marker = {"kind": "baseline", "row": o, "after": after, "status": None}
        if discover_path:
            marker["status"] = "matched" if ident in discovered else "missed"
        if match_path:
            marker["served"] = served.get(o["id"], "")
            marker["offer"] = offers.get(marker["served"])
        chats[key]["markers"][after].append(marker)
        chats[key]["meta"] = o

    for ident in sorted(discovered - baseline):
        visitor_id, session_id, chat_id, after = ident
        key = (visitor_id, session_id, chat_id)
        chats[key]["markers"][int(after)].append(
            {"kind": "new", "row": None, "after": int(after), "status": "new"}
        )

    counts = {
        "baseline": len(baseline),
        "matched": len(baseline & discovered) if discover_path else 0,
        "missed": len(baseline - discovered) if discover_path else 0,
        "new": len(discovered - baseline) if discover_path else 0,
        "filled": sum(1 for v in served.values() if v and v in offers),
        "unknown_offer": sum(1 for v in served.values() if v and v not in offers),
    }

    # Chats with the most going on first.
    ordered = sorted(
        chats.items(),
        key=lambda kv: (-sum(len(v) for v in kv[1]["markers"].values()), -len(kv[1]["messages"])),
    )
    return ordered, counts


def render_slot(marker, note=None):
    kind = marker["kind"]
    status = marker.get("status")
    o = marker["row"]

    if kind == "new":
        bits = [
            '<span class="slot-label">NEW OPPORTUNITY</span>',
            '<span class="dim">you found this one; it is not in the baseline</span>',
        ]
        return f'<div class="slot new">{"".join(bits)}</div>'

    detail = note or f'after assistant message {marker["after"]}'
    geo = ", ".join(x for x in (o.get("geo_city"), o.get("geo_country_name")) if x and x != "null")

    label = "AD SLOT"
    if status == "matched":
        label = "AD SLOT &middot; you found it"
    elif status == "missed":
        label = "AD SLOT &middot; you missed it"

    bits = [
        f'<span class="slot-label">{label}</span>',
        f'<code>{html.escape(o["id"])}</code>',
        f'<span class="dim">{html.escape(detail)}'
        + (f" &middot; {html.escape(geo)}" if geo else "")
        + f' &middot; {html.escape(o.get("device_type") or "")}</span>',
    ]

    if "served" in marker:
        bits.append(render_served(marker))

    css = f"slot {status}" if status else "slot"
    return f'<div class="{css}">{"".join(bits)}</div>'


def render_served(marker):
    """The offer the candidate chose for this slot, if any."""
    offer_id, offer = marker["served"], marker.get("offer")

    if not offer_id:
        return '<div class="served none">no fill &mdash; nothing served here</div>'
    if offer is None:
        return (
            f'<div class="served bad">offer {html.escape(offer_id)} '
            f"is not in offers.csv</div>"
        )

    payout = offer["Payout Amount"].strip()
    pct = offer["Payout Percentage"].strip()
    if payout in ("$0.00", "0", "") and pct not in ("0%", ""):
        payout = f"{pct} rev share"
    url = offer["Preview URL"].strip()

    return (
        '<div class="served">'
        f'<span class="offer-id">#{html.escape(offer_id)}</span>'
        f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(offer["Name"])}</a>'
        f'<span class="dim">{html.escape(offer["Payout Type"])} &middot; {html.escape(payout)}</span>'
        "</div>"
    )


def render_chat(key, chat):
    visitor_id, session_id, chat_id = key
    markers = dict(chat["markers"])
    n_markers = sum(len(v) for v in markers.values())
    meta = chat["meta"]

    parts = []
    seen_assistant = 0
    for m in chat["messages"]:
        role = m["role"]
        parts.append(
            f'<div class="msg {html.escape(role)}">'
            f'<span class="who">{html.escape(role)}</span>'
            f'<p dir="auto">{html.escape(m["text"])}</p>'
            f"</div>"
        )
        if role == "assistant":
            seen_assistant += 1
            for marker in markers.pop(seen_assistant, []):
                parts.append(render_slot(marker))

    # A slot can sit past the last assistant message we have; show it at the end.
    for leftover in sorted(markers):
        for marker in markers[leftover]:
            parts.append(
                render_slot(marker, note=f"after assistant message {leftover} (beyond this transcript)")
            )

    geo = f'{meta.get("geo_city", "")} {meta.get("geo_country_code", "")}'.strip() if meta else ""
    badge = (
        f'<span class="badge">{n_markers} slot{"" if n_markers == 1 else "s"}</span>'
        if n_markers
        else ""
    )

    return (
        f'<details class="chat" data-slots="{n_markers}">'
        f"<summary>"
        f'<code>chat {html.escape(chat_id)}</code> {badge}'
        f'<span class="dim">{len(chat["messages"])} messages'
        + (f" &middot; {html.escape(geo)}" if geo else "")
        + f' &middot; visitor {html.escape(visitor_id[:8])} &middot; session {html.escape(session_id[:8])}</span>'
        f"</summary>"
        f'<div class="thread">{"".join(parts)}</div>'
        f"</details>"
    )


CSS = """
:root { color-scheme: light dark; --bg:#fff; --fg:#16181d; --dim:#6b7280; --line:#e5e7eb;
        --user:#f3f4f6; --asst:#eef4ff;
        --slot:#fff7e6; --slotline:#f59e0b;
        --new:#ecfdf5; --newline:#10b981;
        --miss:#f9fafb; --missline:#9ca3af;
        --bad:#fef2f2; --badline:#ef4444; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111318; --fg:#e6e8ee; --dim:#9aa1ad; --line:#282c35;
          --user:#1b1e25; --asst:#182231;
          --slot:#2a2115; --slotline:#b4790f;
          --new:#122820; --newline:#0f9e6e;
          --miss:#1a1c21; --missline:#6b7280;
          --bad:#2a1618; --badline:#c04040; }
}
* { box-sizing: border-box; }
body { margin:0; padding:24px; background:var(--bg); color:var(--fg); max-width:900px;
       font:14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
h1 { font-size:18px; margin:0 0 4px; }
a { color:inherit; }
.dim { color:var(--dim); font-weight:400; font-size:12px; }
.bar { position:sticky; top:0; background:var(--bg); padding:12px 0; border-bottom:1px solid var(--line);
       margin-bottom:8px; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
input[type=search] { flex:1; min-width:200px; padding:7px 10px; border:1px solid var(--line);
                     border-radius:6px; background:var(--bg); color:var(--fg); font-size:14px; }
label { font-size:13px; color:var(--dim); display:flex; gap:6px; align-items:center; cursor:pointer; }
.legend { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--dim); margin:0 0 10px; }
.legend i { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:5px; }
.chat { border-bottom:1px solid var(--line); padding:8px 0; }
summary { cursor:pointer; display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
summary code { font-size:13px; font-weight:600; }
.badge { background:var(--slotline); color:#fff; border-radius:10px; padding:1px 8px; font-size:11px; }
.thread { padding:10px 0 4px 14px; }
.msg { border-radius:8px; padding:8px 11px; margin:6px 0; background:var(--user); }
.msg.assistant { background:var(--asst); }
.msg p { margin:2px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; }
.who { font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); }
.slot { border:1px dashed var(--slotline); background:var(--slot); border-radius:8px;
        padding:9px 11px; margin:8px 0; display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
.slot.new     { border-color:var(--newline);  background:var(--new); }
.slot.missed  { border-color:var(--missline); background:var(--miss); }
.slot-label { font-size:10px; letter-spacing:.08em; font-weight:700; color:var(--slotline); }
.slot.new .slot-label    { color:var(--newline); }
.slot.missed .slot-label { color:var(--missline); }
.slot code { font-size:12px; }
.served { flex-basis:100%; margin-top:6px; padding:7px 9px; border-radius:6px; background:var(--bg);
          border:1px solid var(--line); display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
.served a { font-weight:600; text-decoration:none; }
.served a:hover { text-decoration:underline; }
.offer-id { font:600 11px ui-monospace, SFMono-Regular, Menlo, monospace; color:var(--dim); }
.served.none { color:var(--dim); font-style:italic; }
.served.bad { border-color:var(--badline); background:var(--bad); }
"""

JS = """
const q = document.getElementById('q');
const onlySlots = document.getElementById('only');
const chats = [...document.querySelectorAll('.chat')];
function apply() {
  const term = q.value.toLowerCase();
  let shown = 0;
  for (const c of chats) {
    const ok = (!onlySlots.checked || c.dataset.slots !== '0')
            && (!term || c.textContent.toLowerCase().includes(term));
    c.hidden = !ok;
    if (ok) shown++;
  }
  document.getElementById('count').textContent = shown + ' chats shown';
}
q.addEventListener('input', apply);
onlySlots.addEventListener('change', apply);
apply();
"""


def build_legend(match_path, discover_path):
    items = []
    if discover_path:
        items += [
            ("--slotline", "matched &mdash; a known opportunity you also found"),
            ("--missline", "missed &mdash; a known opportunity you did not find"),
            ("--newline", "new &mdash; an opportunity you found that the baseline lacks"),
        ]
    else:
        items.append(("--slotline", "a known ad opportunity"))
    if match_path:
        items.append(("--line", "the offer you served, shown inside the slot"))
    return '<p class="legend">' + "".join(
        f'<span><i style="background:var({var})"></i>{text}</span>' for var, text in items
    ) + "</p>"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="chats.html", help="output file (default: chats.html)")
    ap.add_argument("--match", metavar="CSV", help="your Part 1 output; shows the offer served in each slot")
    ap.add_argument("--discover", metavar="CSV", help="your Part 2 output; diffs it against the known opportunities")
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args()

    chats, counts = build_chats(args.match, args.discover)
    with_slots = sum(1 for _, c in chats if c["markers"])

    summary = [f'{len(chats)} chats &middot; {with_slots} carry an ad slot']
    if args.discover:
        summary.append(
            f'{counts["matched"]} of {counts["baseline"]} known opportunities found, '
            f'{counts["missed"]} missed, {counts["new"]} new'
        )
    else:
        summary.append(f'{counts["baseline"]} known opportunities')
    if args.match:
        served = f'{counts["filled"]} slots filled'
        if counts["unknown_offer"]:
            served += f' ({counts["unknown_offer"]} referencing unknown offers)'
        summary.append(served)

    body = "".join(render_chat(k, c) for k, c in chats)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chats &amp; ad opportunities</title>
<style>{CSS}</style></head><body>
<h1>Chats &amp; ad opportunities</h1>
<p class="dim">{' &middot; '.join(summary)}</p>
{build_legend(args.match, args.discover)}
<div class="bar">
  <input type="search" id="q" placeholder="Search messages, ids, offers, cities&hellip;">
  <label><input type="checkbox" id="only" checked> only chats with ad slots</label>
  <span class="dim" id="count"></span>
</div>
{body}
<script>{JS}</script>
</body></html>"""

    with open(args.out, "w") as f:
        f.write(page)

    print(f"Wrote {args.out}: {len(chats)} chats, {with_slots} carrying an ad slot")
    if args.discover:
        print(f"  discovery: {counts['matched']} matched, {counts['missed']} missed, {counts['new']} new")
    if args.match:
        print(f"  matching:  {counts['filled']} slots filled")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(args.out))


if __name__ == "__main__":
    main()
