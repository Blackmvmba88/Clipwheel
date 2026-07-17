from pathlib import Path
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
