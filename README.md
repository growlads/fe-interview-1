# Affiliate Ad Network

## Background

We're building an ad network that serves in-chat ads powered by affiliate offers. A user chats with an AI assistant, and at certain moments we have the opportunity to show them a relevant ad.

Your job is to build the system that decides **what** to show and **whether** to show anything at all.

---

## Data

All files are in the `data/` directory.

| File | Description | Rows |
|------|-------------|------|
| `offers.csv` | Catalog of affiliate offers | ~499 |
| `ad-opportunities.csv` | Known ad opportunities from a live publisher | ~121 |
| `chat-data.csv` | Chat conversations from the same publisher | ~16,000 |

---

## The Task

### Part 1: Ad Matching

Each row in `ad-opportunities.csv` is a moment where you *can* show an ad. Decide which offer to serve for each one - or decide not to serve anything.

The engine should support an `ad_load` parameter.

**Output:** a CSV with columns `ad_slot_id,offer_id`

**Evaluate:**

```bash
python evaluate.py match <your-output.csv>
python evaluate.py match <your-output.csv> --ad-load 0.5
```

---

### Part 2: Opportunity Discovery

The opportunities in `ad-opportunities.csv` are the ones our current system identified. There may be more moments in the chat data where an ad could be shown.

Scan the conversations in `chat-data.csv` and identify additional ad opportunities.

**Output:** a CSV with columns `visitor_id,session_id,chat_id,assistant_message_count`

**Evaluate:**
```bash
python evaluate.py discover <your-output.csv>
```

---

## References

- **THE-ADTECH-BOOK.pdf** — included in this repo. Covers ad tech fundamentals.

---

## Submission

1. Share a link to your **GitHub repo** with your code, output files, and a writeup explaining your approach and decisions.
2. **Export your interactions** with any coding agents/assistants you used and include the transcript (or a link to it) in the repo.
3. Include your output CSVs so we can run the evaluation script.
