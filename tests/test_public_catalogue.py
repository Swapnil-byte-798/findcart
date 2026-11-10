import gzip
import json
from pathlib import Path

from findcart.service import Catalogue, Product


def test_public_catalogue_validates_and_searches_with_real_filters(tmp_path):
    path = Path(__file__).parents[1] / "examples/uci_catalogue.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        products = json.load(stream)
    assert len(products) == 3898
    assert len({item["id"] for item in products}) == len(products)
    catalogue = Catalogue(tmp_path / "public.db")
    for product in products:
        Product.model_validate(product)
        assert "CustomerID" not in product
        catalogue.upsert(product)
    catalogue.sync(rebuild=True)
    result = catalogue.search("red bag under 5", currency="GBP")
    assert result["results"]
    for product in result["results"]:
        assert product["currency"] == "GBP"
        assert float(product["price"]) <= 5
        assert product["color"] == "red"
