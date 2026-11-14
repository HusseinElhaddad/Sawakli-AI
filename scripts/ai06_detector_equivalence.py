"""Compare every original diagnostic field with the actual PR-base detector.

Run with PYTHONPATH=apps/backend/src:apps/backend, --base-ref <actual-PR-base-SHA>.
The additive metric_evidence field is deliberately excluded from the old shape.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import fields
from types import ModuleType

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.features import engineer_features
from tests.fixtures.ai02_benchmark import dataset_digest, evaluate_results, generate_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args()
    path = "apps/backend/src/sawakli/ai/anomaly/detector.py"
    source = subprocess.check_output(["git", "show", f"{args.base_ref}:{path}"], text=True)
    original = ModuleType("ai06_original_detector")
    sys.modules[original.__name__] = original
    exec(compile(source, f"{args.base_ref}:{path}", "exec"), original.__dict__)
    names = [field.name for field in fields(original.AnomalyResult)]
    for seed in (20261015, 20261016):
        benchmark = generate_benchmark(seed)
        features = engineer_features(benchmark.records)
        previous = original.detect_anomalies(features)
        current = detect_anomalies(features)
        before = [[str(getattr(row, name)) for name in names] for row in previous]
        after = [[str(getattr(row, name)) for name in names] for row in current]
        if before != after:
            raise AssertionError(f"diagnostic regression for seed {seed}")
        report = evaluate_results(benchmark, current)
        if report["status"] != "PASS":
            raise AssertionError(report)
        print(
            json.dumps(
                {
                    "base_ref": args.base_ref,
                    "seed": seed,
                    "identical_diagnostics": len(current),
                    "diagnostic_sha256": hashlib.sha256(json.dumps(before).encode()).hexdigest(),
                    "dataset_sha256": dataset_digest(benchmark),
                    "benchmark": report,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
