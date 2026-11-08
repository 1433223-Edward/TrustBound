# PENDING ONLY. No paid execution authorized by this batch.
# Read-only configuration checks (do not submit tasks):
Set-Location D:\Projects\TrustBound
.\.venv\Scripts\python.exe benchmarks/benchmark.py B --manifest benchmarks/configs/B.json
.\.venv\Scripts\python.exe benchmarks/benchmark.py C --manifest benchmarks/configs/C.json
.\.venv\Scripts\python.exe benchmarks/benchmark.py D --manifest benchmarks/configs/D-on.json

# Future submission commands: DO NOT RUN until manifests, fixed batch approval,
# actual models, exact request counts, total cost cap and server budgets are verified.
# .\.venv\Scripts\python.exe benchmarks/benchmark.py B --manifest benchmarks/configs/B.json --execute --allow-paid-inference
# .\.venv\Scripts\python.exe benchmarks/benchmark.py C --manifest benchmarks/configs/C.json --execute --allow-paid-inference
# .\.venv\Scripts\python.exe benchmarks/benchmark.py D --manifest benchmarks/configs/D-on.json --execute --allow-paid-inference
