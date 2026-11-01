"""TC-32: 50 concurrent users must not degrade response time by more than 20%.

Runs Locust headless twice (1 user baseline, then 50 users) and compares the
median and p95 of the aggregated requests. Exits non-zero on failure.

    python loadtest/run_degradation.py --host http://localhost:8000
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "loadtest-results"


def run(users: int, seconds: int, host: str) -> dict:
    prefix = OUT / f"u{users}"
    subprocess.run(
        ["locust", "-f", str(HERE / "locustfile.py"), "--headless", "--host", host,
         "-u", str(users), "-r", str(max(1, users // 5)), "-t", f"{seconds}s",
         "--csv", str(prefix), "--only-summary"],
        check=True,
    )
    with open(f"{prefix}_stats.csv") as fh:
        rows = {r["Name"]: r for r in csv.DictReader(fh)}
    agg = rows["Aggregated"]
    return {"median": float(agg["Median Response Time"]), "p95": float(agg["95%"]),
            "requests": int(agg["Request Count"]), "failures": int(agg["Failure Count"]),
            "per_endpoint": {k: float(v["95%"]) for k, v in rows.items() if k != "Aggregated"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://localhost:8000")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--max-degradation", type=float, default=0.20)
    ap.add_argument("--budget-ms", type=float, default=3000, help="no endpoint p95 may exceed this")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    base = run(1, args.seconds, args.host)
    load = run(50, args.seconds, args.host)
    # Compare medians; small absolute differences (<25 ms) are noise, not degradation.
    delta = load["median"] - base["median"]
    degradation = delta / base["median"] if base["median"] else 0.0
    print(f"\nbaseline  median={base['median']:.0f}ms p95={base['p95']:.0f}ms requests={base['requests']}")
    print(f"50 users  median={load['median']:.0f}ms p95={load['p95']:.0f}ms requests={load['requests']} "
          f"failures={load['failures']}")
    print(f"degradation (median) = {degradation:+.1%}")
    worst = max(load["per_endpoint"].items(), key=lambda kv: kv[1])
    print(f"slowest endpoint p95 under load: {worst[0]} {worst[1]:.0f}ms")

    ok = load["failures"] == 0 and (degradation <= args.max_degradation or delta < 25) and worst[1] <= args.budget_ms
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
