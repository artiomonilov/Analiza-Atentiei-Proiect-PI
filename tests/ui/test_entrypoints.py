import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["--ui-demo", "--demo"])
def test_full_entrypoint_without_optional_imports(mode):
    code = r'''
import importlib.abc
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'cv2', 'torch', 'torchvision', 'sklearn'}:
            raise AssertionError('Import optional interzis in demo: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
from PySide6.QtCore import QTimer
import audience_analysis.ui.main_window as ui
Original = ui.MainWindow
windows = []
class AutoCloseWindow(Original):
    def __init__(self, engine):
        super().__init__(engine)
        windows.append(self)
        engine.result_ready.connect(lambda result: QTimer.singleShot(0, self.close))
        QTimer.singleShot(0, self.start_source)
ui.MainWindow = AutoCloseWindow
from audience_analysis.__main__ import main
assert main() == 0
assert windows and windows[0].history.records
assert windows[0].engine.is_shutdown
print('SIMULARE: fereastra, rezultat, inchidere verificate')
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", code, mode], capture_output=True, encoding="utf-8", env=env, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "inchidere verificate" in result.stdout
    assert "QThread: Destroyed" not in result.stderr
