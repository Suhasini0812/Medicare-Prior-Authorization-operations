"""Page boundaries never change the matching population or its summary."""

import unittest

import pandas as pd

from src.pagination import paginate_requests


class PaginationTests(unittest.TestCase):
    def test_page_boundaries_and_complete_coverage(self):
        rows = pd.DataFrame({"PA_Request_ID": range(53)})
        pages = [paginate_requests(rows, number, 25) for number in (1, 2, 3)]
        self.assertEqual([len(page.rows) for page in pages], [25, 25, 3])
        self.assertEqual([(page.first, page.last) for page in pages], [(1, 25), (26, 50), (51, 53)])
        self.assertTrue(pd.concat([page.rows for page in pages]).equals(rows))
        self.assertEqual(paginate_requests(rows, 99, 25).number, 3)
        self.assertEqual(paginate_requests(rows, -1, 25).number, 1)

    def test_empty_and_invalid_size(self):
        empty = paginate_requests(pd.DataFrame(), 12, 25)
        self.assertEqual((empty.number, empty.pages, empty.first, empty.last), (1, 1, 0, 0))
        self.assertTrue(empty.rows.empty)
        with self.assertRaises(ValueError):
            paginate_requests(pd.DataFrame(), 1, 0)
