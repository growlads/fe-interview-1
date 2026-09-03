# Affiliate Ad Network

## Background

We're building an ad network that serves in-chat ads powered by affiliate offers. A user chats with an AI assistant, and at certain moments we have the opportunity to show them a relevant ad.

Your job is to build the system that decides **what** to show and **whether** to show anything at all.

---

## Data

All three files are in the `data/` directory. The same data is also in
[this spreadsheet](https://docs.google.com/spreadsheets/d/11aIr7U20uaSfOn1zUPjZgq7unlgEab7tRb2C9qEDR1s/edit?gid=1407212167#gid=1407212167)
if you would rather read it there - it is a copy for browsing, not a separate source.

| File | Description | Rows |
|------|-------------|------|
| `data/offers.csv` | Catalog of affiliate offers | 500 |
| `data/ad-opportunities.csv` | Known ad opportunities from a live publisher | 121 |
| `data/chat-data.csv` | Chat conversations from the same publisher | 2,171 |

### Linking the Data

- A single chat is identified by `visitor_id` and `chat_id` across `ad-opportunities.csv` and `chat-data.csv`.
- Geo information for an opportunity is available in the `ad-opportunities.csv` sheet.
- Geo information for an offer is available in the offer title in `offers.csv`.
- An opportunity's `slot_data` is a snapshot of the conversation at the moment the ad
  request fired, so `assistant_message_count: 3` means "after the 3rd assistant message",
  not "this chat has 3 assistant messages". One conversation can hold several
  opportunities at different points.

### Seeing the Data

To read the conversations with their ad slots marked in place:

```bash
python visualize.py --open
```

This writes `chats.html` - every chat, with a placeholder drawn wherever a known
ad opportunity fired. Useful for getting a feel for the traffic before you write
any matching logic.

Once you have output, the same viewer will show it in context:

```bash
python visualize.py --match part1.csv        # the offer you served, inside each slot
python visualize.py --discover part2.csv     # your opportunities vs. the known ones
python visualize.py --match part1.csv --discover part2.csv --open
```

`--match` puts the offer name, payout and preview link in the slot, and marks the
ones you left empty. `--discover` colours each slot by how it compares to the
baseline - matched, missed, or new - and adds the opportunities you found that the
baseline does not have.

To see all of that before you have written anything, `examples/` holds a pair of
well-formed outputs:

```bash
python visualize.py --match examples/part1-random.csv \
                    --discover examples/part2-random.csv --open
```

**The offers in them are picked at random.** They exist to show you the file
formats and to exercise the viewer - not to hint at an approach. Random matching
is a bad answer that still produces a healthy-looking 66% fill rate, which is the
point made in the note below.

---

## Getting Started

Clone this repo before attempting the exercise:

```bash
git clone <repo-url>
cd growl-interview
```

---

## The Task

### Part 1: Ad Matching

Each row in `ad-opportunities.csv` is a moment where you *can* show an ad. Decide which offer to serve for each one - or decide not to serve anything.

**Output:** a CSV with columns `ad_slot_id,offer_id`

**Check your output:**

```bash
python validate.py match <your-output.csv>
```

---

### Part 2: Opportunity Discovery

The opportunities in `ad-opportunities.csv` are the ones our current system identified. There may be more moments in the chat data where an ad could be shown.

Scan the conversations in `chat-data.csv` and identify additional ad opportunities.

**Output:** a CSV with columns `visitor_id,session_id,chat_id,assistant_message_count`

**Check your output:**
```bash
python validate.py discover <your-output.csv>
```

---

## A Note on `validate.py`

`validate.py` is a format checker, not a grader. It confirms your columns are right
and your IDs exist. It does **not** judge whether your ads are well matched, and the
numbers it prints are descriptive statistics rather than a score.

Please don't optimise for them:

- **Fill rate** rises if you serve an ad into every slot. Plenty of these slots have no
  sensible offer behind them - some geos have almost no eligible inventory - and
  choosing to serve nothing is a legitimate answer we're specifically interested in.
- **Discovery count** rises if you flag every assistant message. The 121 known
  opportunities are one system's opinion, not ground truth; neither matching them nor
  beating them on volume is the goal.

We read the writeup. Explain what you optimised for, what you traded away, and where
your approach would break.

---

## References

- **THE-ADTECH-BOOK.pdf** — included in this repo. Covers ad tech fundamentals.

---

## Submission

1. Share a link to your **GitHub repo** with your code, output files, and a writeup explaining your approach and decisions.
2. **Export your interactions** with any coding agents/assistants you used and include the transcript (or a link to it) in the repo.
3. Include your output CSVs so we can run `validate.py` against them.
