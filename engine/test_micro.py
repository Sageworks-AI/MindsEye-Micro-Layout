"""Minimal end-to-end test for mindseye micro."""
import json, os, tempfile, unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import ledger, make_sample, match, measure


class MicroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.docs = self.dir / "docs"
        self.data = self.dir / "data"
        os.environ["MICRO_FIXED_TIME"] = "2026-01-01T00:00:00Z"
        make_sample.make(self.docs / "sample.docx")
        measure.run(self.docs, self.data)
        match.run(self.data)
        self.led = self.data / "ledger" / "events.jsonl"

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("MICRO_FIXED_TIME", None)

    def _check_expected(self):
        exp = json.loads(Path("tests/expected.json").read_text(encoding="utf-8"))["events"]
        got = ledger.read(self.led)
        self.assertEqual(len(got), len(exp))
        for e, x in zip(got, exp):
            self.assertEqual(e["type"], x["type"])
            self.assertEqual(e["source"], x["source"])
            if "shape" in x:
                self.assertEqual(e["shape"], x["shape"])
            self.assertEqual(e["count"], x["count"])
            if "drift_max" in x:
                self.assertLessEqual(e["drift"], x["drift_max"])
            if "drift_min" in x:
                self.assertGreaterEqual(e["drift"], x["drift_min"])

    def test_expected_events(self):
        self._check_expected()

    def test_idempotent_and_append_only(self):
        before = self.led.read_text(encoding="utf-8")
        n = len(before.splitlines(keepends=True))
        measure.run(self.docs, self.data)
        match.run(self.data)
        after = self.led.read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(len(after.splitlines(keepends=True)), n)

    def test_pair_restructure(self):
        n = len(ledger.read(self.led))
        pair = "pair:docs/sample.docx#s1|docs/sample.docx#s2"
        for _ in range(3):
            ledger.append(self.led, "window_compared", pair,
                          detail={"a_option": "texture", "b_option": "text"})
        match.run(self.data)
        new = ledger.read(self.led)[n:]
        fired = [e for e in new if e["type"] == "restructured" and e["source"] == pair]
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["count"], 3)
        root = ET.parse(self.data / "views" / "options.xml").getroot()
        self.assertEqual(root.get("state"), "grouped")

    def test_view_xml(self):
        secs = ET.parse(self.data / "views" / "sample.xml").getroot().findall("section")
        self.assertEqual(len(secs), 3)
        for s in secs:
            says = s.findtext("says")
            self.assertTrue(says and says.strip())

    def test_ingest(self):
        n = len(ledger.read(self.led))
        self.assertEqual(ledger.ingest(self.led, "seed", "seed: Maun", 42), 1)
        got = ledger.read(self.led)
        self.assertEqual(len(got), n + 1)
        self.assertEqual(got[-1]["type"], "matched")
        self.assertTrue(got[-1]["detail"].get("seed"))
        line = json.dumps({"type": "measured", "source": "docs/x.docx#s1"})
        self.assertEqual(ledger.ingest(self.led, "log", line, 43), 0)


if __name__ == "__main__":
    unittest.main()
