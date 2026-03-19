import os
import shutil
import unittest
from unittest.mock import patch

from pipeline import dedup


class DedupTests(unittest.TestCase):
    def test_filter_unseen_uses_chunked_lookup(self):
        temp_dir = os.path.join(os.getcwd(), "tests", "_tmp_dedup")
        db_path = os.path.join(temp_dir, "papers.db")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        try:
            with patch("pipeline.dedup._db_path", return_value=db_path):
                seen_papers = [
                    {"arxiv_id": f"seen-{index}", "title": f"Seen {index}"}
                    for index in range(1200)
                ]
                dedup.mark_processed(seen_papers)

                incoming = seen_papers + [
                    {"arxiv_id": f"new-{index}", "title": f"New {index}"}
                    for index in range(5)
                ]
                filtered = dedup.filter_unseen(incoming)

            self.assertEqual(len(filtered), 5)
            self.assertEqual(
                {paper["arxiv_id"] for paper in filtered},
                {f"new-{index}" for index in range(5)},
            )
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
