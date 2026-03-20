# Affiliate Ad Network

## Background

We're building an ad network that serves in-chat ads powered by affiliate offers. A user chats with an AI assistant, and at certain moments we have the opportunity to show them a relevant ad.

Your job is to build the system that decides **what** to show, **when** to show it, and **whether** to show anything at all.

---

## Data

All files are in the `data/` directory.

| File | Description | Rows |
|------|-------------|------|
| `offers.csv` | Catalog of affiliate offers (what you can serve) | ~499 |
| `chat-data-3303.csv` | Real chat conversations from a live publisher | ~1600 |
| `ad-slots-3303.csv` | Known ad opportunities: when and to whom an ad can be shown | 117 |
| `ad-opportunities-3303.csv` | Full baseline data (used by evaluation script) | 117 |

### Key relationships

- **`ad-slots-3303.csv`** tells you *when* to show an ad (after which assistant message) and *who* sees it (visitor + geo). Use `visitor_id`, `session_id`, and `chat_id` to look up the corresponding conversation in `chat-data-3303.csv`.
- **`chat-data-3303.csv`** contains the actual conversation messages. Use it along with the offer catalog to decide which ad fits.
- **`offers.csv`** is your ad catalog. Offers are geo-targeted (check the name for country codes like "US", "UK", etc.) and have different payout types (CPA/CPS) and amounts.

---

## References

- **THE-ADTECH-BOOK.pdf** — included in this repo. Covers ad tech fundamentals and can be used as reference material.

---

## The Task

### Part 1: Ad Matching

Given 117 known ad slots, decide which offer to serve for each one (or decide not to serve anything).

**Input:**
- `ad-slots-3303.csv` — each row is a moment where you *can* show an ad. It tells you the visitor, session, chat, which assistant message it follows, and the user's country.
- `chat-data-3303.csv` — the conversation context. Match via `visitor_id`, `session_id`, and `chat_id`.
- `offers.csv` — the offer catalog.

**What to build:**
- An algorithm that picks the best offer for each slot based on conversation context, offer relevance, geo targeting, or any other signals you find useful.
- Support an **`ad_load`** parameter: a percentage (0.0–1.0) controlling what fraction of slots get filled. At `ad_load=1.0`, fill every slot you can. At `ad_load=0.5`, fill roughly half.

**Output:** a CSV with columns `ad_slot_id,offer_id`
- `ad_slot_id`: the `id` from `ad-slots-3303.csv`
- `offer_id`: the `Offer ID` from `offers.csv` (omit or leave empty to skip a slot)

**Evaluate:**
```bash
python evaluate.py match <your-output.csv>
python evaluate.py match <your-output.csv> --ad-load 0.5
```

---

### Part 2: Opportunity Discovery

The 117 slots in `ad-slots-3303.csv` are the opportunities our current system identified. But there may be more moments in the chat data where an ad could be shown.

**Your task:** scan the conversations in `chat-data-3303.csv` and identify additional ad opportunities.

Two approaches (try one or both):
1. **General discovery**: find moments where *any* ad (even one not in `offers.csv`) would be relevant.
2. **Catalog-based discovery**" find moments where a specific offer from `offers.csv` could have been shown but wasn't.

**Output:** a CSV with columns `visitor_id,session_id,chat_id,assistant_message_count`

- Each row is an opportunity you identified.

**Evaluate:**

```bash
python evaluate.py discover <your-output.csv>
```

This compares your discoveries against the baseline to measure recall (how many known opportunities you found) and surfaces new ones.

---

## Submission

1. Share a link to your **GitHub repo** with your code, output files, and a writeup explaining your approach and decisions.
2. **Export your interactions** with any coding agents/assistants you used and include the transcript (or a link to it) in the repo.
3. Include your output CSVs so we can run the evaluation script.
