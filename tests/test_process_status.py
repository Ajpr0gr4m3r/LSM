import os
import subprocess
import sys
import unittest
from unittest.mock import patch
import process_status


class ProcessStatusTests(unittest.TestCase):
    def test_invalid_pid(self):
        for pid in (None, 0, -1, True, '123'):
            self.assertFalse(process_status.process_alive(pid))

    def test_current_process_survives_native_check(self):
        self.assertTrue(process_status.process_alive(os.getpid()))

    def test_child_survives_check_and_exit_is_detected(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
        try:
            self.assertTrue(process_status.process_alive(child.pid))
            self.assertIsNone(child.poll())
        finally:
            child.terminate();child.wait(timeout=10)
        self.assertFalse(process_status.process_alive(child.pid))

    def test_windows_never_uses_kill(self):
        with patch('process_status.sys.platform','win32'), \
             patch('process_status._windows_alive',return_value=True) as check, \
             patch('process_status.os.kill') as kill:
            self.assertTrue(process_status.process_alive(123))
            check.assert_called_once_with(123);kill.assert_not_called()
