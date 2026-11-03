"""联网冒烟测试：对本机配了 Key 的来源（Wikimedia 总是）各跑一次真实 search。不联网时整组跳过。"""
import importlib.util
import os
import socket
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("media_source", SCRIPTS / "media-source.py")
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)


def online():
    try:
        socket.create_connection(("commons.wikimedia.org", 443), timeout=5).close()
        return True
    except OSError:
        return False


ONLINE = online()
CASES = [("pexels", "photo"), ("pexels", "video"), ("pixabay", "photo"), ("pixabay", "video"),
         ("unsplash", "photo"), ("wikimedia", "photo"), ("wikimedia", "video")]


class Live(unittest.TestCase):
    def run_case(self, src, kind):
        if not ONLINE:
            self.skipTest("不联网")
        if src in ms.KEY_ENV and not os.environ.get(ms.KEY_ENV[src], "").strip():
            self.skipTest(f"未设置 {ms.KEY_ENV[src]}")
        cs = ms.api_search(src, "water bottle", kind, None, 3)
        self.assertGreaterEqual(len(cs), 1)
        for c in cs:
            self.assertTrue(c["thumb"], c["key"])
            self.assertTrue(c["files"] and c["files"][0]["url"], c["key"])
            self.assertTrue(c["w"] and c["h"], c["key"])
            self.assertTrue(c["license"], c["key"])


for _s, _k in CASES:
    setattr(Live, f"test_{_s}_{_k}", lambda self, s=_s, k=_k: self.run_case(s, k))

if __name__ == "__main__":
    unittest.main()
