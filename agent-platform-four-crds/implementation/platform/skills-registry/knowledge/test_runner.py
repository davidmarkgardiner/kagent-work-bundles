from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from run import MAX_BYTES, Rejected, invoke, limit_file_size


class RunnerBoundaryTests(unittest.TestCase):
    def test_response_file_limit_stops_child_writes(self):
        with tempfile.TemporaryFile() as output:
            child = subprocess.run([sys.executable, '-c', 'import os; os.write(1,b"x" * (2 * 1024 * 1024)); os.write(1,b"x")'],
                                   stdout=output, stderr=subprocess.DEVNULL, preexec_fn=limit_file_size)
            output.seek(0, 2)
            self.assertNotEqual(child.returncode, 0)
            self.assertLessEqual(output.tell(), MAX_BYTES)

    def test_timeout_stops_descendant_work(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'unexpected-child-work'
            child = 'import pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(1); pathlib.Path(' + repr(str(marker)) + ').touch()'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(10)'
            with self.assertRaisesRegex(Rejected, 'A2ATimeout'):
                invoke([sys.executable, '-c', parent], timeout=0.2)
            time.sleep(1.1)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
