# Affiliate Ad Network

## Background

The goal of this task is to design an ad-network that works on top of affiliate offers and serves in-chat ads. 

We have a catalog of affiliate offers and a dataset of real conversations from a live publisher.

Your job is to build a delivery engine that decides **what** to serve, **when** to serve it, and **whether** to serve anything at all.

---

## Data

All files are in the `data/` directory.

| File | Rows |
|------|------|
| `offers.csv` | ~499 |
| `chat-data-3303.csv` | ~11,000 |
| `ad-opportunities-3303.csv` | ~116 |
| `ad-impressions-3303.csv` | ~116 |
| `ad-clicks-3303.csv` | ~16 |

The `ad-opportunities`, `ad-impressions`, and `ad-clicks` files represent what the current production system did. These are your **baseline for comparison**, not your input.

---

## The Task

### 1. Process the offer catalog

The offers need to be served programmatically. Get them into shape.

### 2. Build the delivery engine

Given a set of chat conversations, your engine should identify when to serve an ad and which offer to serve. It should also know when **not** to serve anything.

The engine should support an `ad_load` parameter.

Here `ad_load` is defined per chat. It's usually a number, but we'll set it as a percentage. It's offers shown as a percentage of opportunities.

### 3. Run it and report results

Run your engine against the chat data. Report your results and compare against the baseline.

---

## Stretch Goals

- Frequency capping per offer (total): an offer can only be clicked on 50 times
- Frequency capping per offer (per day): an offer can only be clicked on 10 times/day

---

## Submission

Include your code, output, and a writeup explaining the decisions you made and why.
