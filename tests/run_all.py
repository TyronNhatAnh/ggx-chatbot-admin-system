#!/usr/bin/env python3
"""Run all 25 sessions in sequence.
   exceptions:
     - If a session 16-20

Usage:
  python tests/run_all.py            # run all
  python tests/run_all.py 1 5 9      # run specific sessions only
"""
import sys
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).parent
# skip session 16-20 since they use a different dataset and would require extra setup
sessions = [f"session_{i:02d}.py" for i in range(1, 26) if i not in range(16, 21)]


# Filter to specific sessions if passed as args
if len(sys.argv) > 1:
    nums = {int(a) for a in sys.argv[1:]}
    sessions = [f"session_{n:02d}.py" for n in sorted(nums)]

python = sys.executable
failed = []

for session_file in sessions:
    path = TESTS_DIR / session_file
    if not path.exists():
        print(f"SKIP (not found): {session_file}")
        continue
    print(f"\n{'#' * 64}")
    print(f"  Running {session_file}")
    print(f"{'#' * 64}")
    result = subprocess.run([python, str(path)])
    if result.returncode != 0:
        failed.append(session_file)

print(f"\n{'=' * 64}")
if failed:
    print(f"FAILED sessions: {', '.join(failed)}")
    sys.exit(1)
else:
    print(f"All {len(sessions)} session(s) completed.")
