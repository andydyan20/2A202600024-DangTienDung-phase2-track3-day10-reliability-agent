from __future__ import annotations

import argparse
import json
from pathlib import Path


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _met(actual: float | None, target: float, higher_is_better: bool = True) -> str:
    if actual is None:
        return "N/A"
    ok = actual >= target if higher_is_better else actual <= target
    return "Yes" if ok else "No"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="reports/metrics.json")
    parser.add_argument("--out", default="reports/final_report.md")
    args = parser.parse_args()
    metrics = json.loads(Path(args.metrics).read_text())
    availability = float(metrics.get("availability", 0.0))
    latency_p95 = float(metrics.get("latency_p95_ms", 0.0))
    fallback_success_rate = float(metrics.get("fallback_success_rate", 0.0))
    cache_hit_rate = float(metrics.get("cache_hit_rate", 0.0))
    recovery_time_ms = metrics.get("recovery_time_ms")
    recovery_time = float(recovery_time_ms) if recovery_time_ms is not None else None

    lines = [
        "# Day 10 Reliability Final Report",
        "",
        "## Architecture",
        "",
        "The gateway checks cache first, routes misses through per-provider circuit breakers, "
        "falls back from primary to backup, and returns a static degradation message only "
        "when every provider path is unavailable.",
        "",
        "```",
        "User Request",
        "  -> Gateway",
        "  -> Cache exact/similar lookup",
        "      -> cache hit: return cached response",
        "      -> cache miss: continue",
        "  -> CircuitBreaker(primary) -> primary provider",
        "      -> open/failure: continue",
        "  -> CircuitBreaker(backup) -> backup provider",
        "      -> open/failure: continue",
        "  -> static fallback response",
        "```",
        "",
        "## Configuration",
        "",
        "| Setting | Value | Reason |",
        "|---|---:|---|",
        "| failure_threshold | 3 | Opens quickly after repeated provider failures. |",
        "| reset_timeout_seconds | 2 | Allows fast local recovery evidence during chaos runs. |",
        "| success_threshold | 1 | A successful half-open probe restores traffic. |",
        "| cache TTL | 300s | Keeps repeated lab queries warm without long stale retention. |",
        "| similarity_threshold | 0.92 | Favors exact or very close reuse to reduce false hits. |",
        "| load_test requests | 100 per scenario | Enough samples to trigger breaker behavior. |",
        "",
        "## SLOs",
        "",
        "| SLI | SLO target | Actual value | Met? |",
        "|---|---|---:|---|",
        f"| Availability | >= 99% | {_pct(availability)} | {_met(availability, 0.99)} |",
        f"| Latency P95 | < 2500 ms | {latency_p95:.2f} | {_met(latency_p95, 2500, False)} |",
        "| Fallback success rate | >= 95% | "
        f"{_pct(fallback_success_rate)} | {_met(fallback_success_rate, 0.95)} |",
        f"| Cache hit rate | >= 10% | {_pct(cache_hit_rate)} | {_met(cache_hit_rate, 0.10)} |",
        "| Recovery time | < 5000 ms | "
        f"{recovery_time if recovery_time is not None else 'N/A'} | "
        f"{_met(recovery_time, 5000, False)} |",
        "",
        "## Metrics Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in metrics.items():
        if key == "scenarios":
            continue
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "## Cache Comparison",
        "",
        "The run includes cache-enabled scenarios and breaker-focused scenarios with cache "
        "disabled so provider failures are visible. Cache hit rate and estimated cost saved "
        "come from the cache-enabled portions of the run.",
        "",
        "| Metric | Observed |",
        "|---|---:|",
        f"| cache_hit_rate | {_pct(cache_hit_rate)} |",
        f"| estimated_cost_saved | {metrics.get('estimated_cost_saved')} |",
        f"| estimated_cost | {metrics.get('estimated_cost')} |",
        "",
        "False-hit guardrail evidence: a cached 2024 refund-policy answer is not reused for "
        "a 2026 refund-policy query, and privacy-like account/balance queries are not cached.",
        "",
        "## Redis Shared Cache",
        "",
        "In-memory cache is process-local, so separate gateway instances do not share warm "
        "responses. `SharedRedisCache` stores query/response hashes with TTL in Redis and "
        "uses the same exact/similar lookup plus privacy and false-hit checks. Redis tests "
        "are skipped unless Redis is running on `localhost:6379`.",
        "",
        "Evidence command:",
        "",
        "```bash",
        "make docker-up",
        "pytest -q tests/test_redis_cache.py",
        "```",
        "",
        "## Chaos Scenarios",
        "",
        "| Scenario | Expected behavior | Status |",
        "|---|---|---|",
    ]
    expected = {
        "primary_timeout_100": "Primary opens; backup serves all traffic.",
        "primary_flaky_50": "Primary opens and recovers; backup handles failures.",
        "all_healthy": "Requests succeed without static fallback.",
        "cache_stale_candidate": "Different-year cache candidate is rejected.",
    }
    for key, value in metrics.get("scenarios", {}).items():
        lines.append(f"| {key} | {expected.get(key, 'Scenario succeeds.')} | {value} |")
    lines += [
        "",
        "## Failure Analysis",
        "",
        "The fallback path works for provider failures, but static fallback can still occur "
        "if every upstream provider fails at the same time. Before production, the gateway "
        "should add provider-specific SLO alerts, request budgets, and durable breaker "
        "state for horizontally scaled deployments.",
        "",
        "## Next Steps",
        "",
        "1. Add concurrent load tests with per-route latency histograms.",
        "2. Store circuit-breaker state in a shared backend for multi-instance deployments.",
        "3. Replace deterministic text similarity with vetted embeddings plus stricter "
        "safety metadata.",
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
