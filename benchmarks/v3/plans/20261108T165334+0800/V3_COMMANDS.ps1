# v3 batch 01 NOT AUTHORIZED. Logs manifests are blocked until freeze and refresh.
Set-Location D:\Projects\TrustBound
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-deepseek-v4.1-flash-1017-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-glm-5.3-flash-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-mimo-v2.6-flash-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-glm-5.3-flash-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-mimo-v2.6-flash-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-deepseek-v4.1-flash-1017-r01.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-mimo-v2.6-flash-r02.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-deepseek-v4.1-flash-1017-r02.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-glm-5.3-flash-r02.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-deepseek-v4.1-flash-1017-r02.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-glm-5.3-flash-r02.json"
.\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-mimo-v2.6-flash-r02.json"

# AFTER fixed batch approval + Logs freeze + configuration verification ONLY:
# Set TRUSTBOUND_WORKSPACE_MODELS to the same approved three-model allowlist before the existing local launcher.
# pwsh -NoProfile -File scripts/start_workspace_preview.ps1 -MaxRuns 56 -MaxModelCalls 24 -MaxOutputTokens 96256
# Stop the confirmed idle old local service before launching; never start a second API worker.
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-deepseek-v4.1-flash-1017-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-glm-5.3-flash-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-mimo-v2.6-flash-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-glm-5.3-flash-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-mimo-v2.6-flash-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-deepseek-v4.1-flash-1017-r01.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-mimo-v2.6-flash-r02.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-deepseek-v4.1-flash-1017-r02.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-inventory-glm-5.3-flash-r02.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-deepseek-v4.1-flash-1017-r02.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-glm-5.3-flash-r02.json" --execute --allow-paid-inference
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py B --manifest "benchmarks\v3\plans\20261108T165334+0800\batch01-manifests\v3-B-logs-mimo-v2.6-flash-r02.json" --execute --allow-paid-inference

# After EACH task: verify accepted server_run_id, exact response_model, usage, cost, schema outcome and cleanup.
# Archive only the new verified raw directory; never replace an existing destination.
# Example after substituting the real emitted client UUID:
# Copy-Item -LiteralPath 'benchmarks/results/raw/<actual-client-uuid>' -Destination 'benchmarks/v3/results/raw/<actual-client-uuid>' -Recurse

# Analyze v3 archival copies only; no model/Docker calls:
# .\.venv\Scripts\python.exe -B benchmarks/benchmark.py check --raw benchmarks/v3/results/raw
# python -B benchmarks/benchmark.py analyze --raw benchmarks/v3/results/raw --out benchmarks/v3/results/processed/batch01-review-01
