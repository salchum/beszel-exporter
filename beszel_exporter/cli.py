from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .aggregate import AGGREGATION_FIELD_NAMES, aggregate_rows, parse_interval
from .client import PocketBaseClient, PocketBaseError
from .env import load_dotenv
from .normalize import normalize_record
from .output import write_csv, write_json
from .record_type import select_record_type

DEFAULT_TIMEZONE = "Asia/Jakarta"
OUTPUT_FORMATS = ("csv", "json")
AGGREGATION_MODES = ("avg", "max")


def parse_datetime(value: str, default_timezone: str = DEFAULT_TIMEZONE) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M")
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "expected date-time like '2026-01-01 08:00' or ISO 8601"
            ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed


def pocketbase_datetime(value: datetime) -> str:
    utc_value = value.astimezone(ZoneInfo("UTC"))
    return utc_value.strftime("%Y-%m-%d %H:%M:%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beszel-exporter",
        description="Export Beszel system metrics for a time range to CSV or JSON.",
    )
    parser.add_argument("--hub-url", required=True, help="Beszel hub URL, e.g. http://localhost:8090")
    parser.add_argument("--system-id", required=True, help="Beszel system record ID")
    parser.add_argument("--start", required=True, type=parse_datetime, help="Start date-time")
    parser.add_argument("--end", required=True, type=parse_datetime, help="End date-time")
    parser.add_argument("--format", choices=OUTPUT_FORMATS, default="csv", help="Output format")
    parser.add_argument("--output", required=True, type=Path, help="Output .csv or .json path")
    parser.add_argument("--interval", help="Aggregation interval: 1m, 5m, 1h, 24h, or 1d")
    parser.add_argument("--aggregate", choices=AGGREGATION_MODES, help="Aggregate rows by interval using avg or max")
    parser.add_argument("--log-file", type=Path, help="Write run summary logs to this file")
    parser.add_argument("--email", help="Beszel email, overrides BESZEL_EMAIL and .env")
    parser.add_argument(
        "--password",
        help="Beszel password, overrides BESZEL_PASSWORD and .env",
    )
    parser.add_argument("--per-page", type=int, default=200, help="PocketBase page size")
    parser.add_argument(
        "--ca-file",
        type=Path,
        help="Path to a CA certificate bundle for private or self-signed HTTPS certificates",
    )
    parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable HTTPS certificate verification. Use only for trusted internal networks.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    logger = build_run_logger(args.log_file)
    dotenv = load_dotenv()
    email = args.email or os.getenv("BESZEL_EMAIL") or dotenv.get("BESZEL_EMAIL")
    password = args.password or os.getenv("BESZEL_PASSWORD") or dotenv.get("BESZEL_PASSWORD")
    ca_file_value = args.ca_file or os.getenv("BESZEL_CA_FILE") or dotenv.get("BESZEL_CA_FILE")
    ca_file = Path(ca_file_value) if ca_file_value else None
    insecure_tls = (
        args.insecure_skip_tls_verify
        or is_truthy(os.getenv("BESZEL_INSECURE_SKIP_TLS_VERIFY"))
        or is_truthy(dotenv.get("BESZEL_INSECURE_SKIP_TLS_VERIFY"))
    )

    if not email:
        raise SystemExit("Missing Beszel email. Set BESZEL_EMAIL in .env/env or pass --email.")
    if not password:
        raise SystemExit("Missing Beszel password. Set BESZEL_PASSWORD in .env/env or pass --password.")
    if args.start > args.end:
        raise SystemExit("--start must be before or equal to --end.")
    if args.per_page < 1 or args.per_page > 500:
        raise SystemExit("--per-page must be between 1 and 500.")
    if bool(args.interval) != bool(args.aggregate):
        raise SystemExit("--interval and --aggregate must be used together.")
    interval = None
    if args.interval:
        try:
            interval = parse_interval(args.interval)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    if ca_file is not None and insecure_tls:
        raise SystemExit("Use either --ca-file or --insecure-skip-tls-verify, not both.")
    if ca_file is not None and not ca_file.exists():
        raise SystemExit(f"CA file not found: {ca_file}")

    logger.info(
        "Export started hub_url=%s system_id=%s start=%s end=%s format=%s output=%s interval=%s aggregate=%s",
        safe_url(args.hub_url),
        args.system_id,
        args.start.isoformat(),
        args.end.isoformat(),
        args.format,
        args.output,
        args.interval,
        args.aggregate,
    )

    client = PocketBaseClient(args.hub_url, verify_tls=not insecure_tls, ca_file=ca_file)
    client.authenticate(email, password)

    start_filter = pocketbase_datetime(args.start)
    end_filter = pocketbase_datetime(args.end)
    source_record_type = select_record_type(args.start, args.end)
    logger.info("Selected source_record_type=%s", source_record_type)
    records = client.fetch_system_stats(
        system_id=args.system_id,
        start=start_filter,
        end=end_filter,
        per_page=args.per_page,
        record_type=source_record_type,
    )
    logger.info("Fetched raw_records=%s", len(records))
    rows = [normalize_record(record, fallback_system_id=args.system_id) for record in records]
    fieldnames = None
    if args.interval and args.aggregate:
        rows = aggregate_rows(rows, args.start, args.end, interval, args.aggregate, source_record_type)
        fieldnames = AGGREGATION_FIELD_NAMES

    if args.format == "csv":
        write_csv(args.output, rows, fieldnames=fieldnames)
    else:
        write_json(args.output, rows)

    if not rows:
        logger.warning("No rows produced; requested range may be outside Beszel retention")
        print(
            "Warning: no records found. The requested range may be outside Beszel retention.",
            file=sys.stderr,
        )
    logger.info("Export finished output_rows=%s output_path=%s", len(rows), args.output)
    print(f"Exported {len(rows)} rows to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except PocketBaseError as exc:
        logger = build_run_logger(args.log_file)
        logger.error("Beszel API error: %s", exc)
        print(f"Beszel API error: {exc}", file=sys.stderr)
        return 1


def is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def build_run_logger(log_file: Path | None) -> logging.Logger:
    logger = logging.getLogger("beszel_exporter.run")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if log_file is None:
        logger.addHandler(logging.NullHandler())
        return logger

    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def safe_url(value: str) -> str:
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))
