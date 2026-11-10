"""A SQL catalogue, incremental search index, and validated query interpretation."""

import base64
from collections import Counter
from decimal import Decimal
from difflib import SequenceMatcher
import json
import math
import re
import threading
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .runtime import Fault, LLM, Store, digest, require

SCHEMA = """
CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, payload TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS changes(sequence INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, payload TEXT);
CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, watermark INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS index_rows(version_id TEXT NOT NULL REFERENCES versions(id), product_id TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(version_id,product_id));
CREATE TABLE IF NOT EXISTS active_index(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version_id TEXT REFERENCES versions(id));
CREATE TABLE IF NOT EXISTS parse_cache(key TEXT PRIMARY KEY, payload TEXT NOT NULL)
"""


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=3000)
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    category: str = Field(default="", max_length=100)
    color: str = Field(default="", max_length=40)
    material: str = Field(default="", max_length=100)
    occasion: str = Field(default="", max_length=100)
    brand: str = Field(default="", max_length=100)
    popularity: int = Field(default=0, ge=0)


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: str = Field(default="", max_length=2000)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    color: str = Field(default="", max_length=40)
    material: str = Field(default="", max_length=100)
    occasion: str = Field(default="", max_length=100)
    category: str = Field(default="", max_length=100)
    sort: str = Field(default="relevance", pattern="^(relevance|price_asc|price_desc)$")

    @model_validator(mode="after")
    def valid_range(self):
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("Minimum price exceeds maximum price")
        return self


def rule_parse(query: str, currency: str = "INR") -> SearchPlan:
    query = require(query, "Search query", 2000).lower()
    maximum = re.search(
        r"(?:under|below|less than|upto|up to|se kam)\s*(?:rs\.?|inr|gbp|usd|[₹£$])?\s*(\d+(?:\.\d{1,2})?)",
        query,
    )
    minimum = re.search(
        r"(?:over|above|more than)\s*(?:rs\.?|inr|gbp|usd|[₹£$])?\s*(\d+(?:\.\d{1,2})?)",
        query,
    )
    color = next(
        (
            word
            for word in ["red", "blue", "black", "white", "green", "pink", "yellow"]
            if re.search(rf"\b{word}\b", query)
        ),
        "",
    )
    material = next(
        (
            word
            for word in ["cotton", "silk", "leather", "wood", "metal"]
            if re.search(rf"\b{word}\b", query)
        ),
        "",
    )
    occasion = "wedding" if "wedding" in query or "shaadi" in query else ""
    keywords = re.sub(
        r"(?:under|below|less than|upto|up to|se kam|over|above|more than)\s*(?:rs\.?|inr|gbp|usd|[₹£$])?\s*\d+(?:\.\d{1,2})?",
        "",
        query,
    )
    for source, target in [
        ("sasta wala", ""),
        ("sasta", ""),
        ("saste", ""),
        ("earphone", "earphone headphones"),
        ("shaadi", "wedding"),
    ]:
        keywords = keywords.replace(source, target)
    keywords = " ".join(
        word
        for word in keywords.split()
        if word not in {"for", "a", "the", "please", "show", "me"}
    )
    return SearchPlan(
        keywords=keywords,
        max_price=maximum[1] if maximum else None,
        min_price=minimum[1] if minimum else None,
        currency=currency,
        color=color,
        material=material,
        occasion=occasion,
        sort="price_asc" if "sasta" in query or "cheap" in query else "relevance",
    )


class Catalogue:
    def __init__(self, path=".data/findcart.db", llm=None):
        self.store = Store(path, SCHEMA)
        self.llm = llm or LLM()
        self._vectors = {}
        self._lock = threading.Lock()
        with self.store.transaction() as connection:
            if connection.execute("SELECT * FROM active_index").fetchone() is None:
                version = str(uuid4())
                connection.execute("INSERT INTO versions VALUES(?,0)", (version,))
                connection.execute("INSERT INTO active_index VALUES(1,?)", (version,))

    def upsert(self, value: dict) -> dict:
        try:
            product = Product.model_validate(value)
        except ValidationError:
            raise Fault("The product does not satisfy the catalogue schema.") from None
        payload = product.model_dump_json()
        with self.store.transaction() as connection:
            old = connection.execute(
                "SELECT revision FROM products WHERE id=?", (product.id,)
            ).fetchone()
            revision = old["revision"] + 1 if old else 1
            connection.execute(
                "INSERT INTO products VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision",
                (product.id, payload, revision),
            )
            connection.execute(
                "INSERT INTO changes(product_id,payload) VALUES(?,?)",
                (product.id, payload),
            )
        return {"id": product.id, "revision": revision}

    def delete(self, identifier: str):
        with self.store.transaction() as connection:
            if connection.execute(
                "DELETE FROM products WHERE id=?", (identifier,)
            ).rowcount:
                connection.execute(
                    "INSERT INTO changes(product_id,payload) VALUES(?,NULL)",
                    (identifier,),
                )

    def sync(self, rebuild: bool = False) -> dict:
        with self.store.transaction() as connection:
            active = connection.execute(
                "SELECT v.* FROM versions v JOIN active_index a ON v.id=a.version_id"
            ).fetchone()
            changes = connection.execute(
                "SELECT * FROM changes WHERE sequence>? ORDER BY sequence",
                (active["watermark"],),
            ).fetchall()
            version = str(uuid4()) if rebuild else active["id"]
            watermark = connection.execute(
                "SELECT COALESCE(MAX(sequence),0) AS mark FROM changes"
            ).fetchone()["mark"]
            if rebuild:
                connection.execute(
                    "INSERT INTO versions VALUES(?,?)", (version, watermark)
                )
                connection.execute(
                    "INSERT INTO index_rows SELECT ?,id,payload FROM products",
                    (version,),
                )
                connection.execute(
                    "UPDATE active_index SET version_id=? WHERE singleton=1", (version,)
                )
            else:
                for change in changes:
                    if change["payload"] is None:
                        connection.execute(
                            "DELETE FROM index_rows WHERE version_id=? AND product_id=?",
                            (version, change["product_id"]),
                        )
                    else:
                        connection.execute(
                            "INSERT INTO index_rows VALUES(?,?,?) ON CONFLICT(version_id,product_id) DO UPDATE SET payload=excluded.payload",
                            (version, change["product_id"], change["payload"]),
                        )
                connection.execute(
                    "UPDATE versions SET watermark=? WHERE id=?", (watermark, version)
                )
        return {
            "version": version,
            "watermark": watermark,
            "changes": len(changes),
            "rebuild": rebuild,
        }

    def parse(self, query: str, currency: str, live: bool) -> SearchPlan:
        key = digest([require(query, "Query", 2000), currency, live])
        if not live:
            return rule_parse(query, currency)
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM parse_cache WHERE key=?", (key,)
            ).fetchone()
        if row:
            return SearchPlan.model_validate_json(row["payload"])
        try:
            plan = SearchPlan.model_validate(
                self.llm.ask(
                    "Extract product search filters. Do not invent a price limit. Schema: "
                    + json.dumps(SearchPlan.model_json_schema()),
                    {"query": query, "currency": currency},
                )
            )
        except ValidationError:
            raise Fault("The model returned invalid search filters.", 502) from None
        if plan.currency != currency:
            raise Fault("The model changed the requested currency.", 502)
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO parse_cache VALUES(?,?)",
                (key, plan.model_dump_json()),
            )
        return plan

    def search(
        self,
        query: str,
        currency="INR",
        live=False,
        limit=10,
        cursor: str | None = None,
    ) -> dict:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise Fault("Limit must be between 1 and 100.")
        plan = self.parse(query, currency, live)
        with self.store.transaction() as connection:
            active = dict(
                connection.execute(
                    "SELECT v.* FROM versions v JOIN active_index a ON v.id=a.version_id"
                ).fetchone()
            )
            products = [
                json.loads(row["payload"])
                for row in connection.execute(
                    "SELECT payload FROM index_rows WHERE version_id=? ORDER BY product_id",
                    (active["id"],),
                )
            ]
        fingerprint = digest([query, plan.model_dump(mode="json"), active])
        after = None
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if decoded["query"] != fingerprint:
                    raise Fault("Search or index changed; restart pagination.", 409)
                after = decoded["after"]
            except (ValueError, KeyError, TypeError):
                raise Fault("Invalid search cursor.") from None
        ranked = self._rank(
            products, plan.keywords, (active["id"], active["watermark"])
        )
        filtered = []
        for product, score in ranked:
            price = Decimal(product["price"])
            if (
                product["currency"] != plan.currency
                or plan.max_price is not None
                and price > plan.max_price
                or plan.min_price is not None
                and price < plan.min_price
            ):
                continue
            if any(
                getattr(plan, field)
                and getattr(plan, field).casefold() != product[field].casefold()
                for field in ["color", "material", "occasion", "category"]
            ):
                continue
            if plan.keywords and score <= 0:
                continue
            filtered.append({**product, "score": round(score, 8)})
        if plan.sort != "relevance":
            filtered.sort(
                key=lambda item: (
                    Decimal(item["price"]) * (-1 if plan.sort == "price_desc" else 1),
                    item["id"],
                )
            )
        facets = {
            field: dict(Counter(item[field] for item in filtered if item[field]))
            for field in ["category", "brand", "color"]
        }
        start = 0
        if after is not None:
            positions = [
                index
                for index, product in enumerate(filtered)
                if product["id"] == after
            ]
            if not positions:
                raise Fault("The cursor no longer matches a result.", 409)
            start = positions[0] + 1
        page = filtered[start : start + limit]
        next_cursor = (
            base64.urlsafe_b64encode(
                json.dumps({"query": fingerprint, "after": page[-1]["id"]}).encode()
            ).decode()
            if page and start + len(page) < len(filtered)
            else None
        )
        return {
            "query": query,
            "plan": plan.model_dump(mode="json"),
            "mode": "live_parse" if live else "rules_parse",
            "index": active,
            "total": len(filtered),
            "results": page,
            "facets": facets,
            "next_cursor": next_cursor,
            "ranking": "BM25 + character TF-IDF; lexical, not neural semantic embeddings",
        }

    def _rank(self, products, query, version):
        if not products:
            return []
        documents = [
            " ".join(
                str(product[field])
                for field in [
                    "title",
                    "description",
                    "category",
                    "brand",
                    "color",
                    "material",
                    "occasion",
                ]
            )
            for product in products
        ]
        if not query.strip():
            return [(product, 1.0) for product in products]
        with self._lock:
            if version not in self._vectors:
                vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
                matrix = vectorizer.fit_transform(documents)
                self._vectors = {version: (vectorizer, matrix)}
            vectorizer, matrix = self._vectors[version]
        similarities = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
        tokens = [re.findall(r"\w+", text.casefold()) for text in documents]
        average = sum(map(len, tokens)) / len(tokens)
        words = re.findall(r"\w+", query.casefold())
        document_frequencies = Counter(
            word for document in tokens for word in set(document)
        )
        scores = []
        for index, (product, document) in enumerate(zip(products, tokens)):
            frequencies = Counter(document)
            bm25 = 0.0
            for word in words:
                df = document_frequencies[word]
                count = frequencies[word]
                bm25 += (
                    math.log(1 + (len(tokens) - df + 0.5) / (df + 0.5))
                    * count
                    * 2.2
                    / (count + 1.2 * (0.25 + 0.75 * len(document) / max(average, 1)))
                )
            score = bm25 + float(similarities[index])
            if bm25 == 0 and not any(
                SequenceMatcher(None, word, candidate).ratio() >= 0.72
                for word in words
                if len(word) >= 3
                for candidate in frequencies
            ):
                score = 0.0
            scores.append((product, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]["id"]))

    def autocomplete(self, prefix: str) -> list[str]:
        prefix = require(prefix, "Prefix", 100).casefold()
        with self.store.transaction() as connection:
            rows = connection.execute("SELECT payload FROM products").fetchall()
        candidates = [json.loads(row["payload"]) for row in rows]
        candidates = [
            item
            for item in candidates
            if any(word.startswith(prefix) for word in item["title"].casefold().split())
        ]
        return [
            item["title"]
            for item in sorted(
                candidates, key=lambda item: (-item["popularity"], item["title"])
            )[:10]
        ]
