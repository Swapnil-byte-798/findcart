"""Derive a public product snapshot without copying customer identifiers."""

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import argparse
import gzip
import json
from pathlib import Path
import re
from zipfile import ZipFile

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
archive = parser.parse_args().archive
with ZipFile(archive) as bundle:
    member = next(name for name in bundle.namelist() if name.endswith(".xlsx"))
    with bundle.open(member) as stream:
        workbook = openpyxl.load_workbook(stream, read_only=True, data_only=True)
        rows = workbook.active.iter_rows(values_only=True)
        header = next(rows)
        products = {}
        popularity = Counter()
        counts = Counter()
        for row in rows:
            counts["source_rows"] += 1
            invoice, stock, description, quantity, at, price = row[:6]
            stock = str(stock)
            if str(invoice).upper().startswith("C") or not re.fullmatch(
                r"\d{5}[A-Za-z]?", stock
            ):
                continue
            if (
                not isinstance(description, str)
                or not description.strip()
                or not isinstance(price, (int, float))
                or price <= 0
                or quantity <= 0
            ):
                continue
            counts["eligible_transactions"] += 1
            popularity[stock] += int(quantity)
            previous = products.get(stock)
            if previous and previous["_at"] > at:
                continue
            text = description.strip().title()
            color = next(
                (
                    word
                    for word in [
                        "red",
                        "blue",
                        "black",
                        "white",
                        "green",
                        "pink",
                        "yellow",
                    ]
                    if re.search(rf"\b{word}\b", text, re.I)
                ),
                "",
            )
            products[stock] = {
                "id": stock,
                "title": text,
                "price": str(
                    Decimal(str(price)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                ),
                "currency": "GBP",
                "category": "gifts",
                "color": color,
                "description": "Historical product description from UCI Online Retail.",
                "_at": at,
            }
        workbook.close()
for stock, product in products.items():
    product.pop("_at")
    product["popularity"] = popularity[stock]
output = ROOT / "examples/uci_catalogue.json.gz"
with gzip.GzipFile(
    filename="", mode="wb", fileobj=output.open("wb"), mtime=0
) as stream:
    stream.write(
        (
            json.dumps(list(products.values()), ensure_ascii=False, indent=2) + "\n"
        ).encode()
    )
metadata = {
    **counts,
    "products": len(products),
    "currency": "GBP",
    "source": "https://archive.ics.uci.edu/dataset/352/online+retail",
    "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "derivation": "Latest positive-price non-cancelled positive-quantity line per physical StockCode; exclude customer identifiers; colour is a literal description match.",
    "historical_period": "2010-2011; not current stock or current prices",
}
(ROOT / "evidence/data_source.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata))
