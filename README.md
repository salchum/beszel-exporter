# Beszel Exporter

Export Beszel `system_stats` records for one system and time range to CSV or JSON.

## Usage

Create a local `.env` file for Beszel user credentials. You can start from the
example file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
BESZEL_EMAIL=you@example.com
BESZEL_PASSWORD=your-password
```

The `.env` file is ignored by Git because it contains secrets. The exporter reads
`.env` from the directory where you run the command.

Credential precedence is:

1. `--email` and `--password` CLI flags
2. Shell environment variables
3. Values from `.env`

This means you can temporarily override `.env` without editing the file:

```bash
BESZEL_EMAIL=other@example.com BESZEL_PASSWORD=other-password python3 -m beszel_exporter ...
```

Run the exporter:

```bash
python3 -m beszel_exporter \
  --hub-url http://localhost:8090 \
  --system-id SYSTEM_ID \
  --start "2026-01-01 08:00" \
  --end "2026-01-01 11:00" \
  --format csv \
  --output bandwidth_report.csv
```

Naive date-times are treated as `Asia/Jakarta` and sent to PocketBase as UTC.
Timezone-aware ISO date-times are also supported.

## Output Format

Use `--format csv` to create a SQL-friendly CSV file with one header row and one
metric row per Beszel `system_stats` record.

Use `--format json` to create a JSON array containing the same flat row objects.

CSV example:

```csv
timestamp,system_id,record_type,cpu_usage,memory_usage,memory_used,disk_usage,disk_used,bandwidth_upload,bandwidth_download,cumulative_upload,cumulative_download
2026-01-01 01:00:00.000Z,abc123,1m,12.5,64.2,2048,70.1,120.5,2.4,5.1,123456,654321
```

JSON example:

```json
[
  {
    "timestamp": "2026-01-01 01:00:00.000Z",
    "system_id": "abc123",
    "record_type": "1m",
    "cpu_usage": 12.5,
    "memory_usage": 64.2,
    "memory_used": 2048,
    "disk_usage": 70.1,
    "disk_used": 120.5,
    "bandwidth_upload": 2.4,
    "bandwidth_download": 5.1,
    "cumulative_upload": 123456,
    "cumulative_download": 654321
  }
]
```

## Output Fields

`timestamp`, `system_id`, `record_type`, `cpu_usage`, `memory_usage`, `memory_used`,
`disk_usage`, `disk_used`, `bandwidth_upload`, `bandwidth_download`,
`cumulative_upload`, `cumulative_download`.

Field mapping from Beszel stats:

| Output field | Beszel source | Description |
| --- | --- | --- |
| `timestamp` | record `created` | Record timestamp returned by Beszel. |
| `system_id` | record `system` | Beszel system ID. |
| `record_type` | record `type` | Beszel rollup type, such as `1m` when present. |
| `cpu_usage` | `stats.cpu` | CPU usage. |
| `memory_usage` | `stats.m`, fallback `stats.mp` | Memory usage percentage. |
| `memory_used` | `stats.mu` | Memory used. |
| `disk_usage` | `stats.dp` | Disk usage percentage. |
| `disk_used` | `stats.du` | Disk used. |
| `bandwidth_upload` | `stats.ns` | Upload/network sent rate. |
| `bandwidth_download` | `stats.nr` | Download/network received rate. |
| `cumulative_upload` | `stats.b[0]` | Cumulative uploaded bytes. |
| `cumulative_download` | `stats.b[1]` | Cumulative downloaded bytes. |

## Notes

Beszel keeps historical records according to its retention policy. If the requested
range is older than retained data, the exporter writes an empty CSV/JSON file and
prints a warning.
