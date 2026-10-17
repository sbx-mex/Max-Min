import json
from pathlib import Path
import subprocess
import unittest


class WorkerTests(unittest.TestCase):
    def test_fresh_data_http_errors_offline_and_cache_limits(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(['node', 'tools/tests/service_worker.cjs'], cwd=root, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'ok')
