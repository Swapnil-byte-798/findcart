from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from pydantic import ValidationError
from findcart.cli import PRODUCTS
from findcart.runtime import Fault
from findcart.service import Catalogue, SearchPlan, rule_parse


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.catalogue = Catalogue(Path(self.directory.name) / "test.db")
        for product in PRODUCTS:
            self.catalogue.upsert(product)
        self.catalogue.sync()

    def tearDown(self):
        self.directory.cleanup()

    def test_price_color_material_and_occasion(self):
        result = self.catalogue.search("red cotton kurta under 2000 for a wedding")
        self.assertEqual([item["id"] for item in result["results"]], ["demo-kurta-red"])

    def test_price_is_not_invented_for_cheap(self):
        plan = rule_parse("sasta wala bluetooth earphone")
        self.assertIsNone(plan.max_price)
        self.assertEqual(plan.sort, "price_asc")

    def test_hinglish_keyword_search(self):
        result = self.catalogue.search("sasta wala bluetooth earphone")
        self.assertEqual(result["results"][0]["id"], "demo-headphones")

    def test_typo_character_retrieval(self):
        self.assertEqual(
            self.catalogue.search("headphons")["results"][0]["id"], "demo-headphones"
        )

    def test_facets_match_filtered_results(self):
        result = self.catalogue.search("kurta under 2000")
        self.assertEqual(result["facets"]["category"], {"clothing": 1})

    def test_no_cross_currency_results(self):
        self.assertEqual(self.catalogue.search("kurta", currency="GBP")["total"], 0)

    def test_update_is_invisible_before_sync(self):
        self.catalogue.upsert(PRODUCTS[0] | {"price": "5000.00"})
        self.assertEqual(self.catalogue.search("kurta under 2000")["total"], 1)
        self.catalogue.sync()
        self.assertEqual(self.catalogue.search("kurta under 2000")["total"], 0)

    def test_delete_sync_removes_index_row(self):
        self.catalogue.delete("demo-headphones")
        self.catalogue.sync()
        self.assertEqual(self.catalogue.search("bluetooth earphone")["total"], 0)

    def test_rebuild_preserves_results_and_switches_version(self):
        before = self.catalogue.search("kurta")
        self.catalogue.sync(rebuild=True)
        after = self.catalogue.search("kurta")
        self.assertEqual(before["results"], after["results"])
        self.assertNotEqual(before["index"]["id"], after["index"]["id"])

    def test_cursor_paginates_without_duplicates(self):
        first = self.catalogue.search("kurta", limit=1)
        second = self.catalogue.search("kurta", limit=1, cursor=first["next_cursor"])
        self.assertNotEqual(first["results"][0]["id"], second["results"][0]["id"])
        self.assertIsNone(second["next_cursor"])

    def test_cursor_is_bound_to_query(self):
        cursor = self.catalogue.search("kurta", limit=1)["next_cursor"]
        with self.assertRaises(Fault):
            self.catalogue.search("headphones", cursor=cursor)

    def test_cursor_invalidates_after_index_change(self):
        cursor = self.catalogue.search("kurta", limit=1)["next_cursor"]
        self.catalogue.delete("demo-kurta-red")
        self.catalogue.sync()
        with self.assertRaises(Fault):
            self.catalogue.search("kurta", cursor=cursor)

    def test_autocomplete(self):
        self.assertEqual(
            self.catalogue.autocomplete("blu"), ["Bluetooth earphone headphones"]
        )

    def test_invalid_price_and_range(self):
        with self.assertRaises(Fault):
            self.catalogue.upsert(PRODUCTS[0] | {"price": "-1"})
        with self.assertRaises(ValidationError):
            SearchPlan(min_price=10, max_price=5)

    def test_duplicate_updates_have_one_product(self):
        self.catalogue.upsert(PRODUCTS[0])
        self.catalogue.sync()
        self.assertEqual(self.catalogue.search("kurta")["total"], 2)

    def test_invalid_cursor_and_page_size(self):
        for args in [{"cursor": "!invalid!"}, {"limit": 0}, {"limit": 101}]:
            with self.subTest(args=args), self.assertRaises(Fault):
                self.catalogue.search("kurta", **args)

    def test_model_filter_parse_is_cached(self):
        class Parser:
            calls = 0

            def ask(self, *args):
                self.calls += 1
                return SearchPlan(keywords="kurta", max_price=2000).model_dump(
                    mode="json"
                )

        parser = Parser()
        self.catalogue.llm = parser
        first = self.catalogue.search("kurta cheap", live=True)
        self.catalogue.search("kurta cheap", live=True)
        self.assertEqual(parser.calls, 1)
        self.assertEqual(first["total"], 1)

    def test_invalid_model_filter_cannot_reach_search(self):
        class Parser:
            def ask(self, *args):
                return {"keywords": "kurta", "max_price": -1}

        self.catalogue.llm = Parser()
        with self.assertRaises(Fault):
            self.catalogue.search("kurta", live=True)

    def test_index_survives_new_service(self):
        reopened = Catalogue(self.catalogue.store.path)
        self.assertEqual(reopened.search("kurta")["total"], 2)

    def test_empty_index_is_valid(self):
        empty = Catalogue(Path(self.directory.name) / "empty.db")
        self.assertEqual(empty.search("anything")["results"], [])
