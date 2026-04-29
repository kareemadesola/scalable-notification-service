# Prometheus & Grafana Monitoring Guide

How to use the built-in observability stack to monitor the notification service in real time.

---

## Overview

The stack ships with two monitoring tools:

| Tool | URL | Purpose |
|------|-----|---------|
| **Prometheus** | `http://localhost:9090` | Collects and stores metrics, run ad-hoc queries |
| **Grafana** | `http://localhost:3000` | Visual dashboards built on top of Prometheus |

Prometheus scrapes `http://localhost:8000/metrics` every 15 seconds automatically.

---

## Accessing the Raw Metrics

```bash
curl http://localhost:8000/metrics
```

Prometheus uses a plain-text format. Each metric looks like:

```
# HELP http_requests_total Total number of requests by method, status and handler.
# TYPE http_requests_total counter
http_requests_total{handler="/notifications",method="POST",status_code="201"} 5.0
```

- `# HELP` — human-readable description
- `# TYPE` — `counter` (always increases), `gauge` (can go up/down), `histogram` (buckets)
- The line below is the actual value with **labels** in `{}`

---

## Available Metrics

### HTTP Traffic (from prometheus-fastapi-instrumentator)

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total requests, labelled by `handler`, `method`, `status_code` |
| `http_request_duration_seconds` | Histogram | Request latency per endpoint (few buckets) |
| `http_request_duration_highr_seconds` | Histogram | High-resolution latency for accurate percentiles (no per-handler labels) |
| `http_request_size_bytes` | Summary | Size of incoming request bodies |
| `http_response_size_bytes` | Summary | Size of outgoing response bodies |

### Process / Runtime

| Metric | Description |
|--------|-------------|
| `process_cpu_seconds_total` | CPU time used by the API process |
| `process_resident_memory_bytes` | RAM currently in use |
| `process_virtual_memory_bytes` | Virtual memory allocated |
| `process_open_fds` | Number of open file descriptors |
| `python_gc_objects_collected_total` | Python garbage collector activity |

---

## Prometheus UI — Running Queries

Open **`http://localhost:9090`** → click the **search bar** → type a query → click **Execute**.

Switch between **Table** (current values) and **Graph** (over time).

---

### Essential Queries

#### 1. Total request count per endpoint

```promql
http_requests_total
```

Shows every endpoint + method + status code combination and how many times each was hit since startup.

---

#### 2. Request rate (requests per second, rolling 1 minute)

```promql
rate(http_requests_total[1m])
```

> `rate()` = calculates how fast a counter is increasing per second | `[1m]` = look back over the last 1 minute

Click **Graph** to see live traffic over time.

---

#### 3. Error rate (5xx responses only)

```promql
rate(http_requests_total{status_code=~"5.."}[1m])
```

> `status_code=~"5.."` = regex match — any status code starting with 5

---

#### 4. p95 latency across all endpoints

```promql
histogram_quantile(0.95, rate(http_request_duration_highr_seconds_bucket[5m]))
```

> `histogram_quantile(0.95, ...)` = 95th percentile — 95% of requests complete faster than this value | `[5m]` = rolling 5-minute window

This is the most useful single number for understanding API performance.

---

#### 5. p50 and p99 latency (median and tail)

```promql
histogram_quantile(0.50, rate(http_request_duration_highr_seconds_bucket[5m]))
histogram_quantile(0.99, rate(http_request_duration_highr_seconds_bucket[5m]))
```

---

#### 6. Average request duration per endpoint

```promql
rate(http_request_duration_seconds_sum[1m])
/
rate(http_request_duration_seconds_count[1m])
```

> Divides total time spent (sum) by number of requests (count) = average latency per handler

---

#### 7. Request rate per endpoint (to see which route is busiest)

```promql
sum by (handler) (rate(http_requests_total[1m]))
```

> `sum by (handler)` = aggregate all method/status combinations, group only by endpoint path

---

#### 8. API memory usage

```promql
process_resident_memory_bytes / 1024 / 1024
```

> Divides bytes by 1024 twice to convert to megabytes

---

#### 9. CPU usage rate

```promql
rate(process_cpu_seconds_total[1m])
```

> Returns the fraction of a CPU core in use (0.1 = 10% of one core)

---

## Grafana Dashboard

Open **`http://localhost:3000`**

- **Username:** `admin`
- **Password:** `admin` (or `GRAFANA_PASSWORD` from `.env`)

The **Notification Service** dashboard is pre-provisioned automatically. It includes:

| Panel | Query used |
|-------|-----------|
| Request Rate | `rate(http_requests_total[1m])` |
| p95 Latency | `histogram_quantile(0.95, ...)` |
| Error Rate | `rate(http_requests_total{status_code=~"5.."}[1m])` |
| Active Connections | Process file descriptors |

### Changing the time range

Use the **time picker** in the top-right corner (e.g. "Last 15 minutes", "Last 1 hour"). Click **Refresh** or set auto-refresh to 10s while load testing.

---

## Generating Load to See Metrics

Run this in your terminal to send 20 notifications and populate the graphs:

```bash
TOKEN=$(docker exec ns_api python3 -c "from auth import create_access_token; print(create_access_token('demo'))")

for i in {1..20}; do
  curl -s -X POST http://localhost:8000/notifications \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"347f7697-af76-48e5-be73-f966bab92ae5","type":"transactional","channel":"email","subject":"Load test","body":"Message number '"$i"'."}' > /dev/null
  echo "Sent $i"
done
```

> `for i in {1..20}` = loop from 1 to 20 | `> /dev/null` = discard the response so the terminal stays clean | `'"$i"'` = inject the loop counter into the string

Then open Prometheus and run:

```promql
rate(http_requests_total[1m])
```

You'll see the spike in the graph.

---

## Prometheus Targets (Health Check)

Open **`http://localhost:9090/targets`** to confirm Prometheus is successfully scraping the API.

You should see:

```
http://api:8000/metrics   UP   15s ago
```

If it shows `DOWN`, check that `ns_api` is running:

```bash
docker ps --filter name=ns_api --format "{{.Names}}\t{{.Status}}"
```

---

## Stopping and Restarting Monitoring

```bash
# Restart just monitoring services
docker compose restart prometheus grafana

# View Prometheus logs
docker logs ns_prometheus --tail 20

# View Grafana logs
docker logs ns_grafana --tail 20
```
