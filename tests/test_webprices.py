import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live import webprices  # noqa: E402
from dips_score.sources import undermine, wowauctions  # noqa: E402

SAMPLE = (Path(__file__).parent / "wowauctions_14099.json").read_text(encoding="utf-8")
PAGE = ('<html><head><script id="__NEXT_DATA__" type="application/json">' + SAMPLE +
        '</script></head><body></body></html>')
# constructed from the documented {request, result} shape, not captured: no key on this PC
REALMS_RETAIL = {"request": {}, "result": {"us": [{"slug": "area-52", "name": "Area 52"}], "eu": []}}
REALMS_FOREVER = {"request": {}, "result": {"us": [{"slug": "pvp-forever-us", "name": "Forever PvP"}]}}
ITEM = {"request": {}, "result": {"min": 150, "median": 180, "lastUpdated": "2026-11-26T06:00:00Z"}}


class Fake:
    """urlopen stand-in: answers by URL, counts calls"""
    def __init__(self, answers):
        self.answers, self.urls = answers, []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        for part, body in self.answers.items():
            if part in req.full_url:
                if isinstance(body, Exception):
                    raise body
                return io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
        raise OSError("offline")


class Parse(unittest.TestCase):
    def test_page(self):
        self.assertEqual(wowauctions.parse_page(PAGE), {"min": 200100, "median": 196, "count": 5,
                                                        "seen": "2026-11-26T06:26:25Z", "name": "Native Sash"})

    def test_broken(self):
        self.assertIsNone(wowauctions.parse_page("<html>Not found</html>"))
        self.assertIsNone(wowauctions.parse_page(PAGE.replace('"v2"', '"v3"')))
        self.assertIsNone(wowauctions.parse_page(PAGE.replace('"props"', '"props" "', 1)))

    def test_undermine(self):
        self.assertEqual(undermine.forever(undermine.parse_realms(REALMS_RETAIL)), [])
        self.assertEqual(undermine.forever(undermine.parse_realms(REALMS_FOREVER))[0]["slug"], "pvp-forever-us")
        self.assertEqual(undermine.parse_item(ITEM)["min"], 150)
        self.assertIsNone(undermine.parse_item({"result": {}}))
        self.assertEqual(undermine.parse_realms("junk"), [])


class Refresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = mock.Mock(data_dir=Path(self.tmp.name))
        self.settings = {"web_prices": True, "web_server": "forever-us", "web_realm": "pvp",
                         "web_faction": "alliance", "undermine_key": ""}
        mock.patch.object(wowauctions.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.tmp.cleanup)

    def run_with(self, fake, ids, now):
        with mock.patch("urllib.request.urlopen", fake):
            return webprices.refresh(self.paths, self.settings, ids, now=now)

    def test_off(self):
        self.settings["web_prices"] = False
        fake = Fake({})
        self.run_with(fake, [14099], 10_000)
        self.assertEqual(fake.urls, [])

    def test_hour_and_merge(self):
        fake = Fake({"/14099": PAGE.encode()})
        self.assertIn("1 of 2", self.run_with(fake, [14099, 2], 10_000))
        self.assertIn("https://www.wowauctions.net/auctionHouse/forever-us/pvp-forever-us/alliance/14099", fake.urls)
        self.assertEqual(webprices.cached(self.paths)[14099]["min"], 200100)
        self.assertIn("min ago", self.run_with(fake, [2], 10_000 + 1800))
        self.assertEqual(len(fake.urls), 2)
        offline = Fake({})      # an hour later and offline: the old prices stay
        self.run_with(offline, [14099], 10_000 + 3700)
        self.assertEqual(webprices.cached(self.paths)[14099]["source"], "wowauctions")

    def test_undermine_without_forever(self):
        self.settings["undermine_key"] = "k"
        fake = Fake({"realms.json": REALMS_RETAIL, "/14099": PAGE.encode()})
        self.assertIn("Undermine has no Forever realms", self.run_with(fake, [14099], 10_000))
        self.assertEqual([u for u in fake.urls if "undermine" in u], ["https://api.undermine.exchange/v1/static/realms.json"])

    def test_undermine_first(self):
        self.settings["undermine_key"] = "k"
        fake = Fake({"realms.json": REALMS_FOREVER, "/item/14099": ITEM})
        self.run_with(fake, [14099], 10_000)
        self.assertEqual(webprices.cached(self.paths)[14099], {"min": 150, "median": 180,
                                                               "seen": "2026-11-26T06:00:00Z", "source": "undermine"})
        self.assertFalse(any("wowauctions" in u for u in fake.urls))

    def test_never_raises(self):
        (Path(self.tmp.name) / "webprices.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(webprices.cached(self.paths), {})
        with mock.patch.object(webprices.store, "write_file", side_effect=PermissionError):
            self.assertIn("failed", webprices.refresh(self.paths, self.settings, [1], now=10_000))


if __name__ == "__main__":
    unittest.main()
