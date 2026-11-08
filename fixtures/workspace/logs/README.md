# Application Log Summary

Correct log classification and interval filtering. The entry point is `logs.py:solve`. Each line has a decimal minute, a level and a message. Count the parsed level within the half-open interval from start to end. Count malformed lines separately. Output all three supported levels, including zeros.

Only `logs.py` is editable. Use the Workspace sample to load the public and protected cases. The original should fail due to a false ERROR and inclusive upper bound. The offline repair should pass. Inspect the per-case outputs and cleanup evidence in the Workspace report.
