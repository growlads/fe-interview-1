#!/usr/bin/env python3
"""
Evaluation script for the Affiliate Ad Network interview task.

Usage:
    # Part 1: Evaluate ad matching results
    python evaluate.py match <your-output.csv>

    # Part 2: Evaluate discovered opportunities
    python evaluate.py discover <your-output.csv>

Expected output formats:

    Part 1 (match): CSV with columns: ad_slot_id, offer_id
        - ad_slot_id: id from ad-slots-3303.csv
        - offer_id: Offer ID from offers.csv (leave empty or omit row to skip)

    Part 2 (discover): CSV with columns: visitor_id, session_id, chat_id, assistant_message_count
        - Each row is an ad opportunity you identified in the chat data
"""

import argparse
import csv
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_offers():
    offers = {}
    with open(os.path.join(DATA_DIR, "offers.csv"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            offer_id = row["Offer ID"].strip()
            offers[offer_id] = row
    return offers


def load_ad_slots():
    slots = {}
    with open(os.path.join(DATA_DIR, "ad-slots-3303.csv"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slots[row["id"]] = row
    return slots


def load_baseline_opportunities():
    """Load the full ad-opportunities file for comparison."""
    opps = []
    with open(os.path.join(DATA_DIR, "ad-opportunities-3303.csv"), "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            opps.append(row)
    return opps


def verify_match(output_path):
    """Verify Part 1: ad matching results."""
    offers = load_offers()
    slots = load_ad_slots()

    # Parse candidate output
    assignments = {}
    with open(output_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row["ad_slot_id"].strip()
            offer_id = row.get("offer_id", "").strip()
            if offer_id:
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
    print("PART 1: AD MATCHING RESULTS")
    print("=" * 60)
    print(f"Total ad slots:          {total_slots}")
    print(f"Slots filled:            {filled}")
    print(f"Fill rate:               {fill_rate:.1%}")
    print()

    if invalid_slots:
        print(f"WARNING: {len(invalid_slots)} invalid slot IDs (not in ad-slots-3303.csv)")
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
    """Verify Part 2: opportunity discovery results."""
    baseline = load_baseline_opportunities()

    # Build baseline set of (visitor_id, session_id, chat_id, assistant_message_count)
    import json
    baseline_set = set()
    for row in baseline:
        slot_data = json.loads(row["slot_data"])
        key = (
            row["visitor_id"],
            row["session_id"],
            str(slot_data.get("chat_id", "")),
            str(slot_data.get("assistant_message_count", "")),
        )
        baseline_set.add(key)

    # Parse candidate output
    discovered = []
    with open(output_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row["visitor_id"].strip(),
                row["session_id"].strip(),
                str(row["chat_id"]).strip(),
                str(row["assistant_message_count"]).strip(),
            )
            discovered.append(key)

    discovered_set = set(discovered)

    # Compare
    overlap = baseline_set & discovered_set
    new_opportunities = discovered_set - baseline_set
    missed = baseline_set - discovered_set

    print("=" * 60)
    print("PART 2: OPPORTUNITY DISCOVERY RESULTS")
    print("=" * 60)
    print(f"Baseline opportunities:  {len(baseline_set)}")
    print(f"Your discoveries:        {len(discovered_set)}")
    print()
    print(f"Overlap with baseline:   {len(overlap)}")
    print(f"  Recall:                {len(overlap) / len(baseline_set):.1%}" if baseline_set else "  Recall: N/A")
    print(f"New opportunities found: {len(new_opportunities)}")
    print(f"Baseline missed:         {len(missed)}")
    print()

    if discovered_set and len(discovered) != len(discovered_set):
        print(f"WARNING: {len(discovered) - len(discovered_set)} duplicate rows in output")
        print()

    print("=" * 60)
    return len(overlap), len(new_opportunities), len(baseline_set)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate interview task results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    match_parser = subparsers.add_parser("match", help="Evaluate Part 1: ad matching")
    match_parser.add_argument("output", help="Path to your output CSV")


    discover_parser = subparsers.add_parser("discover", help="Evaluate Part 2: opportunity discovery")
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
