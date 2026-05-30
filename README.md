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

# Optional, for private/self-signed HTTPS certificates:
# BESZEL_CA_FILE=/path/to/ca.pem

# Optional, only for trusted internal networks:
# BESZEL_INSECURE_SKIP_TLS_VERIFY=false
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

### HTTPS Certificates

If your Beszel hub uses HTTPS with a private or self-signed certificate, Python may
show:

```text
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

Best option: point the exporter to the CA certificate that signed your Beszel
certificate:

```bash
python3 -m beszel_exporter \
  --hub-url https://beszel.example.com \
  --ca-file /path/to/ca.pem \
  --system-id SYSTEM_ID \
  --start "2026-01-01 08:00" \
  --end "2026-01-01 11:00" \
  --format csv \
  --output bandwidth_report.csv
```

You can also set `BESZEL_CA_FILE=/path/to/ca.pem` in `.env`.

For a trusted internal network only, you can skip TLS verification:

```bash
python3 -m beszel_exporter \
  --hub-url https://beszel.example.com \
  --insecure-skip-tls-verify \
  --system-id SYSTEM_ID \
  --start "2026-01-01 08:00" \
  --end "2026-01-01 11:00" \
  --format csv \
  --output bandwidth_report.csv
```

Or set `BESZEL_INSECURE_SKIP_TLS_VERIFY=true` in `.env`.

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

### Log File

Use `--log-file` to write a run summary log:

```bash
python3 -m beszel_exporter \
  --hub-url http://localhost:8090 \
  --system-id SYSTEM_ID \
  --start "2026-01-01 08:00" \
  --end "2026-01-01 11:00" \
  --format csv \
  --output bandwidth_report.csv \
  --log-file logs/export.log
```

The log includes the requested range, selected Beszel source record type, record
counts, output path, warnings, and API errors. It does not log passwords, tokens,
or `.env` contents. Parent directories for the log file are created automatically.

## Aggregation

By default, the exporter writes one row for each Beszel `system_stats` record.
Use `--interval` and `--aggregate` together to group records into report buckets.

Supported intervals:

| Value | Meaning |
| --- | --- |
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `1h` | 1 hour |
| `24h` | 24 hours |
| `1d` | 1 day |

Supported aggregation modes:

| Value | Meaning |
| --- | --- |
| `avg` | Average numeric metric values in each interval. |
| `max` | Maximum numeric metric values in each interval. |

`--interval` controls the output row spacing. The exporter also chooses the
Beszel `system_stats.type` automatically from the total requested time range:

| Requested range | Beszel source `type` |
| --- | --- |
| `<= 1 hour` | `1m` |
| `<= 12 hours` | `10m` |
| `<= 24 hours` | `20m` |
| `<= 7 days` | `120m` |
| `<= 30 days` | `480m` |

Buckets start from the exact `--start` value. For example, if `--start` is
`2026-01-01 11:00` and `--interval 24h`, the first bucket is Jan 1 11:00 to
Jan 2 11:00, the second bucket is Jan 2 11:00 to Jan 3 11:00, and so on.
Every bucket is emitted. If Beszel has no source record in a bucket, that row
has `sample_count` set to `0` and metric values set to `null`.

Max stats every 1 minute:

```bash
python3 -m beszel_exporter \
  --hub-url https://beszel.example.com \
  --system-id SYSTEM_ID \
  --start "2026-01-01 11:00" \
  --end "2026-01-01 14:00" \
  --interval 1m \
  --aggregate max \
  --format csv \
  --output utilization.csv
```

Average stats every 24 hours:

```bash
python3 -m beszel_exporter \
  --hub-url https://beszel.example.com \
  --system-id SYSTEM_ID \
  --start "2026-01-01 11:00" \
  --end "2026-01-30 11:00" \
  --interval 24h \
  --aggregate avg \
  --format json \
  --output utilization.json
```

## Output Format

Use `--format csv` to create a SQL-friendly CSV file with one header row and one
metric row per Beszel `system_stats` record.

Use `--format json` to create a JSON array containing the same flat row objects.

CSV example:

```csv
timestamp,system_id,record_type,cpu_usage,memory_usage,memory_used,disk_usage,disk_used,bandwidth_upload,bandwidth_download,bandwidth_upload_max,bandwidth_download_max,cumulative_upload,cumulative_download
2026-01-01 01:00:00.000Z,abc123,1m,12.5,64.2,2048,70.1,120.5,109,71,268,145,117596082,156853239
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
    "bandwidth_upload": 109,
    "bandwidth_download": 71,
    "bandwidth_upload_max": 268,
    "bandwidth_download_max": 145,
    "cumulative_upload": 117596082,
    "cumulative_download": 156853239
  }
]
```

## Output Fields

`timestamp`, `system_id`, `record_type`, `cpu_usage`, `memory_usage`, `memory_used`,
`disk_usage`, `disk_used`, `bandwidth_upload`, `bandwidth_download`,
`bandwidth_upload_max`, `bandwidth_download_max`, `cumulative_upload`,
`cumulative_download`.

Aggregated output adds these fields:

`interval_start`, `interval_end`, `source_record_type`, `aggregation`, `sample_count`.

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
| `bandwidth_upload` | `stats.b[0]`, fallback `stats.ns` | Upload/network sent rate. |
| `bandwidth_download` | `stats.b[1]`, fallback `stats.nr` | Download/network received rate. |
| `bandwidth_upload_max` | `stats.bm[0]` | Max upload/network sent rate. |
| `bandwidth_download_max` | `stats.bm[1]` | Max download/network received rate. |
| `cumulative_upload` | sum of `stats.ni.*[2]`, fallback `stats.b[0]` | Cumulative uploaded bytes. |
| `cumulative_download` | sum of `stats.ni.*[3]`, fallback `stats.b[1]` | Cumulative downloaded bytes. |

For aggregated output, CPU, memory, disk, and bandwidth rate fields use the
selected `avg` or `max` mode. Cumulative upload/download are reported as bytes
transferred within each bucket: last cumulative value minus first cumulative
value in that interval. If `sample_count` is `0`, metric values are `null`.

## Notes

Beszel keeps historical records according to its retention policy. If the requested
range is older than retained data, the exporter writes an empty CSV/JSON file and
prints a warning.
