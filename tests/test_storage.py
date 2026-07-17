from pathlib import Path
import csv
import json
import tempfile
import unittest

from cleepwheel.storage import ClipboardStore


class ClipboardStoreTest(unittest.TestCase):
    def test_add_list_search_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ClipboardStore(Path(tmp) / "db.sqlite3")
            self.assertTrue(store.add("hello world"))
            self.assertFalse(store.add("hello world"))
            self.assertEqual(store.count(), 1)
            self.assertEqual(store.list(10)[0].content, "hello world")
            self.assertEqual(store.search("world")[0].content, "hello world")
            entry = store.latest()
            self.assertIsNotNone(entry)
            self.assertEqual(store.get(entry.id).content, "hello world")
            self.assertTrue(store.update(entry.id, "hello edited"))
            self.assertEqual(store.get(entry.id).content, "hello edited")
            self.assertTrue(store.delete(entry.id))
            self.assertEqual(store.clear(), 0)
            self.assertEqual(store.count(), 0)

    def test_only_consecutive_duplicates_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ClipboardStore(Path(tmp) / "db.sqlite3")
            self.assertTrue(store.add("first"))
            self.assertFalse(store.add("first"))
            self.assertTrue(store.add("second"))
            self.assertTrue(store.add("first"))
            self.assertEqual([entry.content for entry in store.list()], ["first", "second", "first"])

    def test_export_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ClipboardStore(root / "db.sqlite3")
            store.add("one")
            store.add("two")

            json_path = root / "exports" / "history.json"
            csv_path = root / "exports" / "history.csv"
            self.assertEqual(store.export_json(json_path), 2)
            self.assertEqual(store.export_csv(csv_path), 2)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual([row["content"] for row in payload], ["two", "one"])
            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["content"] for row in rows], ["two", "one"])
