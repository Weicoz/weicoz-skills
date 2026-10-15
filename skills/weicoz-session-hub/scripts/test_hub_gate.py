"""hub-gate 判定逻辑回归；用模拟指标覆盖 macOS／Linux 与 Windows 两种分支，不依赖本机实际负载。"""
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader("hub_gate", str(Path(__file__).with_name("hub-gate")))
spec = importlib.util.spec_from_loader(loader.name, loader)
gate = importlib.util.module_from_spec(spec)
loader.exec_module(gate)

T = {"load": 1.5, "cpu": 85, "mem": 10, "disk": 10, "swap": 15}


def load_metrics(**kw):
    m = {"kind": "load", "load1": 4.0, "ncpu": 10, "mem_free_pct": 40, "swap_gb": 1.0}
    m.update(kw)
    return m


def cpu_metrics(**kw):
    m = {"kind": "cpu", "cpu_pct": 30.0, "mem_free_pct": 40, "swap_gb": 1.0}
    m.update(kw)
    return m


class EvaluateTests(unittest.TestCase):
    def test_all_ok_passes(self):
        rows, code = gate.evaluate(load_metrics(), 50, "/data", T)
        self.assertEqual(code, 0)
        self.assertIn("4.00 ÷ 10 核 = 0.40", rows[0])

    def test_swap_over_blocks(self):
        rows, code = gate.evaluate(load_metrics(swap_gb=17.6), 50, "/data", T)
        self.assertEqual(code, 3)
        self.assertIn("已用交换超标", rows[-1])

    def test_load_over_blocks(self):
        _, code = gate.evaluate(load_metrics(load1=20), 50, "/data", T)
        self.assertEqual(code, 3)

    def test_unknown_metric_returns_2(self):
        rows, code = gate.evaluate(load_metrics(mem_free_pct=None), 50, "/data", T)
        self.assertEqual(code, 2)
        self.assertTrue(any(r.startswith("未确认  空闲内存") for r in rows))

    def test_windows_uses_cpu_and_pagefile(self):
        rows, code = gate.evaluate(cpu_metrics(), 50, r"C:\work", T)
        self.assertEqual(code, 0)
        self.assertTrue(rows[0].startswith("通过  CPU 利用率"))
        self.assertTrue(any("页面文件已用" in r for r in rows))

    def test_windows_cpu_over_blocks(self):
        _, code = gate.evaluate(cpu_metrics(cpu_pct=92.5), 50, r"C:\work", T)
        self.assertEqual(code, 3)

    def test_windows_pagefile_over_blocks(self):
        rows, code = gate.evaluate(cpu_metrics(swap_gb=16), 50, r"C:\work", T)
        self.assertEqual(code, 3)
        self.assertIn("页面文件已用超标", rows[-1])

    def test_disk_low_blocks(self):
        _, code = gate.evaluate(load_metrics(), 5, "/data", T)
        self.assertEqual(code, 3)


class ProbeDispatchTests(unittest.TestCase):
    def test_windows_branch_selected(self):
        fake = {"cpu_pct": 10.0, "mem_free_pct": 50.0, "swap_gb": 0.5}
        with patch.object(gate.platform, "system", return_value="Windows"), \
             patch.object(gate, "probe_windows", return_value=fake):
            self.assertEqual(gate.probe(), {"kind": "cpu", **fake})

    def test_parse_pagefile_output(self):
        self.assertEqual(gate.parse_mb("2048\r\n"), 2048.0)
        self.assertIsNone(gate.parse_mb(""))


if __name__ == "__main__":
    unittest.main()
