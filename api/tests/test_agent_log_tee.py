"""Native runner stderr/stdout remains visible in both the API terminal and log."""
from __future__ import annotations
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from api.services.log_tee import start_log_tee

class LogTeeTests(unittest.TestCase):
    def test_output_is_saved_and_forwarded_to_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'agent.log'
            child=subprocess.Popen([sys.executable,'-u','-c',
                'import sys; print("turn=1/48 · provider completed",flush=True); print("ERROR [graph_recursion_limit] synthetic stack",file=sys.stderr,flush=True)'],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            console=io.StringIO()
            thread=start_log_tee(child,log,console)
            self.assertEqual(child.wait(timeout=5),0)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertIn('turn=1/48',log.read_text())
            self.assertIn('ERROR [graph_recursion_limit]',log.read_text())
            self.assertIn('ERROR [graph_recursion_limit]',console.getvalue())

if __name__=='__main__': unittest.main()
