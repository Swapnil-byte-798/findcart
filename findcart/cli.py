from pathlib import Path
import json
import gzip
import tempfile
from .runtime import run_cli
from .service import Catalogue

PRODUCTS = [
    {
        "id": "demo-kurta-red",
        "title": "Red cotton wedding kurta",
        "price": "1500.00",
        "color": "red",
        "material": "cotton",
        "occasion": "wedding",
        "category": "clothing",
    },
    {
        "id": "demo-kurta-premium",
        "title": "Red cotton wedding kurta premium",
        "price": "2500.00",
        "color": "red",
        "material": "cotton",
        "occasion": "wedding",
        "category": "clothing",
    },
    {
        "id": "demo-headphones",
        "title": "Bluetooth earphone headphones",
        "price": "899.00",
        "color": "black",
        "category": "electronics",
    },
]


def demo():
    with tempfile.TemporaryDirectory() as directory:
        catalogue = Catalogue(Path(directory) / "demo.db")
        for product in PRODUCTS:
            catalogue.upsert(product)
        catalogue.sync()
        return {
            "data": "three authored test products, not a real catalogue",
            "search": catalogue.search("red cotton kurta under 2000 for a wedding"),
        }


def extend(sub):
    ingest = sub.add_parser("import-json")
    ingest.add_argument("path", type=Path)

    def action(args):
        catalogue = Catalogue()
        opener = gzip.open if args.path.suffix == ".gz" else open
        with opener(args.path, "rt", encoding="utf-8") as stream:
            values = json.load(stream)
        for product in values:
            catalogue.upsert(product)
        return catalogue.sync(rebuild=True)

    ingest.set_defaults(action=action)


def main():
    run_cli("findcart", demo, ("GROQ_API_KEY",), extend)
