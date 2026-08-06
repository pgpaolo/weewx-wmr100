#!/usr/bin/env python3
"""Summarize one or more rotating WMR100 developer JSONL trace files."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any, Iterable


def candidate_files(base: Path, backups: int) -> list[Path]:
    result = []
    for index in range(backups, 0, -1):
        rotated = Path(f"{base}.{index}")
        if rotated.is_file():
            result.append(rotated)
    if base.is_file():
        result.append(base)
    return result


def records(paths: Iterable[Path]):
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield path, line_number, {"event": "invalid_json", "error": str(exc)}
                    continue
                if isinstance(item, dict):
                    yield path, line_number, item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--backups", type=int, default=5)
    parser.add_argument("--last", type=int, default=15)
    args = parser.parse_args()

    paths = candidate_files(args.trace, max(0, args.backups))
    if not paths:
        parser.error(f"trace not found: {args.trace}")

    event_counts: collections.Counter[str] = collections.Counter()
    direction_counts: collections.Counter[str] = collections.Counter()
    health_counts: collections.Counter[str] = collections.Counter()
    recent: collections.deque[dict[str, Any]] = collections.deque(maxlen=max(0, args.last))
    total = 0

    for path, line_number, item in records(paths):
        total += 1
        event_counts[str(item.get("event", "unknown"))] += 1
        if item.get("direction") is not None:
            direction_counts[str(item["direction"])] += 1
        if item.get("health_state") is not None:
            health_counts[str(item["health_state"])] += 1
        item = dict(item)
        item["_source"] = f"{path.name}:{line_number}"
        recent.append(item)

    print(f"Files: {', '.join(str(path) for path in paths)}")
    print(f"Records: {total}")

    print("\nEvents:")
    for event, count in event_counts.most_common():
        print(f"  {event:42} {count}")

    if direction_counts:
        print("\nDirections:")
        for direction, count in direction_counts.most_common():
            print(f"  {direction:42} {count}")

    if health_counts:
        print("\nHealth states:")
        for state, count in health_counts.most_common():
            print(f"  {state:42} {count}")

    if recent:
        print("\nMost recent records:")
        for item in recent:
            timestamp = item.get("timestamp_utc", item.get("timestamp", "-"))
            event = item.get("event", "unknown")
            severity = item.get("severity", "-")
            source = item.pop("_source", "-")
            details = {
                key: value for key, value in item.items()
                if key not in {"timestamp_utc", "timestamp", "event", "severity"}
            }
            text = json.dumps(details, ensure_ascii=False, sort_keys=True)
            print(f"  {timestamp} {severity:7} {event:36} {source} {text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
