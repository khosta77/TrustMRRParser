from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from trustmrr_scraper.client import StartupNotFound, TrustMRRClient
from trustmrr_scraper.notifier import EmailNotifier

DROP_FIELDS = ("cofounders", "xProfilePicture", "icon")


def scrape(
    client: TrustMRRClient,
    notifier: EmailNotifier,
    *,
    limit: int | None,
    enrich: bool,
    page_size: int,
    filters: dict[str, str],
) -> list[dict]:
    total = client.total_count(**filters)
    target = total if limit is None else min(limit, total)
    print(f"[start] цель {target} стартапов, enrich={enrich}", flush=True)
    notifier.started(target, enrich)

    startups: list[dict] = []
    next_milestone = 10
    with tqdm(total=target, desc="list", unit="startup") as bar:
        for item in client.iter_startups(limit=page_size, **filters):
            startups.append(item)
            bar.update(1)
            percent = int(len(startups) / target * 100) if target else 0
            if percent >= next_milestone:
                print(f"[progress] список {next_milestone}% ({len(startups)}/{target})", flush=True)
                notifier.progress(next_milestone, len(startups), target, phase="список")
                next_milestone += 10
            if len(startups) >= target:
                break

    if enrich:
        enriched = 0
        next_detail_milestone = 10
        total_detail = len(startups)
        for item in tqdm(startups, desc="detail", unit="startup"):
            try:
                item.update(client.get_startup(item["slug"]))
            except StartupNotFound:
                pass
            enriched += 1
            percent = int(enriched / total_detail * 100) if total_detail else 0
            if percent >= next_detail_milestone:
                print(f"[progress] детали {next_detail_milestone}% ({enriched}/{total_detail})", flush=True)
                notifier.progress(next_detail_milestone, enriched, total_detail, phase="детали")
                next_detail_milestone += 10

    for item in startups:
        for field in DROP_FIELDS:
            item.pop(field, None)

    return startups


def write_json(startups: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count": len(startups),
        "startups": startups,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trustmrr-scrape", description=__doc__)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--out", type=Path, default=Path("data/startups.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--enrich", action="store_true")
    parser.add_argument("--category", default=None)
    parser.add_argument("--sort", default=None)
    parser.add_argument("--on-sale", action="store_true")
    parser.add_argument("--notify-to", default="puwerfulpants@mail.ru")
    parser.add_argument("--no-notify", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    filters: dict[str, str] = {}
    if args.category:
        filters["category"] = args.category
    if args.sort:
        filters["sort"] = args.sort
    if args.on_sale:
        filters["onSale"] = "true"

    notifier = EmailNotifier.from_env(
        dict(os.environ), recipient=args.notify_to, enabled=not args.no_notify
    )

    started_at = time.monotonic()
    try:
        with TrustMRRClient(args.api_key, proxy=args.proxy) as client:
            startups = scrape(
                client,
                notifier,
                limit=args.limit,
                enrich=args.enrich,
                page_size=args.page_size,
                filters=filters,
            )
        write_json(startups, args.out)
    except Exception as exc:  # noqa: BLE001
        notifier.failed(f"{type(exc).__name__}: {exc}")
        print(f"error: {exc}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - started_at
    notifier.completed(len(startups), str(args.out), elapsed)
    print(f"saved {len(startups)} startups -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
