# Day 10 Reliability Final Report

## Architecture

The gateway checks cache first, routes misses through per-provider circuit breakers, falls back from primary to backup, and returns a static degradation message only when every provider path is unavailable.

```
User Request
  -> Gateway
  -> Cache exact/similar lookup
      -> cache hit: return cached response
      -> cache miss: continue
  -> CircuitBreaker(primary) -> primary provider
      -> open/failure: continue
  -> CircuitBreaker(backup) -> backup provider
      -> open/failure: continue
  -> static fallback response
```

## Configuration

| Setting | Value | Reason |
|---|---:|---|
| failure_threshold | 3 | Opens quickly after repeated provider failures. |
| reset_timeout_seconds | 2 | Allows fast local recovery evidence during chaos runs. |
| success_threshold | 1 | A successful half-open probe restores traffic. |
| cache TTL | 300s | Keeps repeated lab queries warm without long stale retention. |
| similarity_threshold | 0.92 | Favors exact or very close reuse to reduce false hits. |
| load_test requests | 100 per scenario | Enough samples to trigger breaker behavior. |

## SLOs

| SLI | SLO target | Actual value | Met? |
|---|---|---:|---|
| Availability | >= 99% | 100.00% | Yes |
| Latency P95 | < 2500 ms | 515.79 | Yes |
| Fallback success rate | >= 95% | 100.00% | Yes |
| Cache hit rate | >= 10% | 39.50% | Yes |
| Recovery time | < 5000 ms | 3015.4902935028076 | Yes |

## Metrics Summary

| Metric | Value |
|---|---:|
| total_requests | 400 |
| availability | 1.0 |
| error_rate | 0.0 |
| latency_p50_ms | 212.02 |
| latency_p95_ms | 515.79 |
| latency_p99_ms | 548.25 |
| fallback_success_rate | 1.0 |
| cache_hit_rate | 0.395 |
| circuit_open_count | 18 |
| recovery_time_ms | 3015.4902935028076 |
| estimated_cost | 0.10416 |
| estimated_cost_saved | 0.158 |

## Cache Comparison

The run includes cache-enabled scenarios and breaker-focused scenarios with cache disabled so provider failures are visible. Cache hit rate and estimated cost saved come from the cache-enabled portions of the run.

| Metric | Observed |
|---|---:|
| cache_hit_rate | 39.50% |
| estimated_cost_saved | 0.158 |
| estimated_cost | 0.10416 |

False-hit guardrail evidence: a cached 2024 refund-policy answer is not reused for a 2026 refund-policy query, and privacy-like account/balance queries are not cached.

## Redis Shared Cache

In-memory cache is process-local, so separate gateway instances do not share warm responses. `SharedRedisCache` stores query/response hashes with TTL in Redis and uses the same exact/similar lookup plus privacy and false-hit checks. Redis tests are skipped unless Redis is running on `localhost:6379`.

Evidence command:

```bash
make docker-up
pytest -q tests/test_redis_cache.py
```

## Chaos Scenarios

| Scenario | Expected behavior | Status |
|---|---|---|
| primary_timeout_100 | Primary opens; backup serves all traffic. | pass |
| primary_flaky_50 | Primary opens and recovers; backup handles failures. | pass |
| all_healthy | Requests succeed without static fallback. | pass |
| cache_stale_candidate | Different-year cache candidate is rejected. | pass |

## Failure Analysis

The fallback path works for provider failures, but static fallback can still occur if every upstream provider fails at the same time. Before production, the gateway should add provider-specific SLO alerts, request budgets, and durable breaker state for horizontally scaled deployments.

## Next Steps

1. Add concurrent load tests with per-route latency histograms.
2. Store circuit-breaker state in a shared backend for multi-instance deployments.
3. Replace deterministic text similarity with vetted embeddings plus stricter safety metadata.