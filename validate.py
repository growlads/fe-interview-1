#!/usr/bin/env python3
"""
Format checker for the Affiliate Ad Network interview task.

This is NOT an evaluation. It only confirms your output is well-formed:
the columns are right, the slot and offer IDs exist, and there are no
duplicate rows. It cannot tell whether the ads you picked are any good, and
the numbers it prints are descriptive statistics, not a score.

In particular, do not optimise for them. Fill rate goes up if you serve an
ad into every slot, and discovery count goes up if you flag every assistant
message - both of which are worse answers, not better ones. Deciding not to
serve is a legitimate and often correct outcome. Your reasoning in the
writeup is what gets read.

Usage:
    # Part 1: Check ad matching output
    python validate.py match <your-output.csv>

    # Part 2: Check discovered opportunities
    python validate.py discover <your-output.csv>

Expected output formats:

    Part 1 (match): CSV with columns: ad_slot_id, offer_id
        - ad_slot_id: id from ad-opportunities.csv
        - offer_id: Offer ID from offers.csv (leave empty or omit row to skip)

    Part 2 (discover): CSV with columns: visitor_id, session_id, chat_id, assistant_message_count
        - Each row is an ad opportunity you identified in the chat data
"""

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")

OPPORTUNITIES_FILE = "ad-opportunities.csv"


def open_data(name):
    """Open a data file from data/ or the repo root, whichever has it."""
    for path in (os.path.join(DATA_DIR, name), os.path.join(ROOT, name)):
        if os.path.exists(path):
            return open(path, newline="")
    print(f"Error: {name} not found in data/ or {ROOT}")
    print("Download it from the spreadsheet linked in README.md and save it to data/.")
    sys.exit(1)


def load_offers():
    offers = {}
    with open_data("offers.csv") as f:
        for row in csv.DictReader(f):
            offers[row["Offer ID"].strip()] = row
    return offers


def load_opportunities():
    """Every ad opportunity: the ad slots of Part 1, the baseline of Part 2."""
    with open_data(OPPORTUNITIES_FILE) as f:
        return list(csv.DictReader(f))


def require_columns(reader, columns, output_path):
    missing = [c for c in columns if c not in (reader.fieldnames or [])]
    if missing:
        print(f"Error: {output_path} is missing column(s): {', '.join(missing)}")
        print(f"Expected header: {','.join(columns)}")
        sys.exit(1)


def norm(value):
    """Normalise a key field so 1, "1" and pandas' "1.0" all compare equal."""
    value = str(value).strip()
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value


def verify_match(output_path):
    """Check Part 1 output: ad matching."""
    offers = load_offers()
    slots = {row["id"]: row for row in load_opportunities()}

    # Parse candidate output
    assignments = {}
    duplicates = []
    with open(output_path, newline="") as f:
        reader = csv.DictReader(f)
        require_columns(reader, ["ad_slot_id", "offer_id"], output_path)
        for row in reader:
            slot_id = row["ad_slot_id"].strip()
            offer_id = (row.get("offer_id") or "").strip()
            if offer_id:
                if slot_id in assignments:
                    duplicates.append(slot_id)
                assignments[slot_id] = offer_id

    total_slots = len(slots)
    filled = 0
    valid = 0
    invalid_slots = []
    invalid_offers = []

    for slot_id, offer_id in assignments.items():
        # Check slot exists
        if slot_id not in slots:
            invalid_slots.append(slot_id)
            continue

        # Check offer exists
        if offer_id not in offers:
            invalid_offers.append(offer_id)
            continue

        filled += 1

    fill_rate = filled / total_slots if total_slots > 0 else 0

    print("=" * 60)
    print("PART 1: AD MATCHING - FORMAT CHECK")
    print("=" * 60)
    print(f"Total ad slots:          {total_slots}")
    print(f"Slots filled:            {filled}")
    print(f"Fill rate:               {fill_rate:.1%}   (a statistic, not a score)")
    print()

    if duplicates:
        print(f"WARNING: {len(duplicates)} duplicate slot IDs in output (last one wins)")
        for s in duplicates[:5]:
            print(f"  - {s}")
        print()

    if invalid_slots:
        print(f"WARNING: {len(invalid_slots)} invalid slot IDs (not in {OPPORTUNITIES_FILE})")
        for s in invalid_slots[:5]:
            print(f"  - {s}")
        if len(invalid_slots) > 5:
            print(f"  ... and {len(invalid_slots) - 5} more")
        print()

    if invalid_offers:
        print(f"WARNING: {len(invalid_offers)} invalid offer IDs (not in offers.csv)")
        for o in invalid_offers[:5]:
            print(f"  - {o}")
        if len(invalid_offers) > 5:
            print(f"  ... and {len(invalid_offers) - 5} more")
        print()

    print("=" * 60)
    return filled, total_slots


def verify_discover(output_path):
    """Check Part 2 output: opportunity discovery."""
    baseline = load_opportunities()

    # Build baseline set of (visitor_id, session_id, chat_id, assistant_message_count)
    baseline_set = set()
    for row in baseline:
        slot_data = json.loads(row["slot_data"])
        key = (
            norm(row["visitor_id"]),
            norm(row["session_id"]),
            norm(slot_data.get("chat_id", "")),
            norm(slot_data.get("assistant_message_count", "")),
        )
        baseline_set.add(key)

    # Parse candidate output
    discovered = []
    with open(output_path, newline="") as f:
        reader = csv.DictReader(f)
        require_columns(
            reader,
            ["visitor_id", "session_id", "chat_id", "assistant_message_count"],
            output_path,
        )
        for row in reader:
            key = (
                norm(row["visitor_id"]),
                norm(row["session_id"]),
                norm(row["chat_id"]),
                norm(row["assistant_message_count"]),
            )
            discovered.append(key)

    discovered_set = set(discovered)

    # Compare
    overlap = baseline_set & discovered_set
    new_opportunities = discovered_set - baseline_set
    missed = baseline_set - discovered_set

    print("=" * 60)
    print("PART 2: OPPORTUNITY DISCOVERY - FORMAT CHECK")
    print("=" * 60)
    print(f"Baseline opportunities:  {len(baseline_set)}")
    print(f"Your discoveries:        {len(discovered_set)}")
    print()
    print(f"Overlap with baseline:   {len(overlap)}")
    print(f"  Recall:                {len(overlap) / len(baseline_set):.1%}" if baseline_set else "  Recall: N/A")
    print(f"New opportunities found: {len(new_opportunities)}")
    print(f"Baseline missed:         {len(missed)}")
    print()
    print("None of the above is a score - the baseline is one system's opinion,")
    print("not ground truth, and a bigger discovery count is not a better answer.")
    print()

    if discovered_set and len(discovered) != len(discovered_set):
        print(f"WARNING: {len(discovered) - len(discovered_set)} duplicate rows in output")
        print()

    print("=" * 60)
    return len(overlap), len(new_opportunities), len(baseline_set)


def main():
    parser = argparse.ArgumentParser(
        description="Check the format of your interview task output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match", help="Check Part 1: ad matching")
    match_parser.add_argument("output", help="Path to your output CSV")


    discover_parser = subparsers.add_parser("discover", help="Check Part 2: opportunity discovery")
    discover_parser.add_argument("output", help="Path to your output CSV")

    args = parser.parse_args()

    if not os.path.exists(args.output):
        print(f"Error: file not found: {args.output}")
        sys.exit(1)

    if args.command == "match":
        verify_match(args.output)
    elif args.command == "discover":
        verify_discover(args.output)


if __name__ == "__main__":
    main()
