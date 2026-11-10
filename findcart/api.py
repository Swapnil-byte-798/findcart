import os
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from .runtime import make_app
from .service import Catalogue, Product

app, auth, reviewer = make_app("FindCart")
_catalogue = None


def service():
    global _catalogue
    path = os.path.join(os.environ.get("DATA_DIR", ".data"), "findcart.db")
    if _catalogue is None or str(_catalogue.store.path) != path:
        _catalogue = Catalogue(path)
    return _catalogue


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")
    live: bool = False
    limit: int = Field(default=10, ge=1, le=100)
    cursor: str | None = None


@app.put("/products/{identifier}", dependencies=[Depends(auth)])
def upsert(identifier: str, product: Product):
    from .runtime import Fault

    if product.id != identifier:
        raise Fault("Product ID does not match the path.")
    return service().upsert(product.model_dump(mode="json"))


@app.delete("/products/{identifier}", dependencies=[Depends(auth)])
def delete(identifier: str):
    service().delete(identifier)
    return {"deleted": identifier}


@app.post("/index/sync", dependencies=[Depends(auth)])
def sync(rebuild: bool = False):
    return service().sync(rebuild)


@app.post("/search", dependencies=[Depends(auth)])
def search(query: Query):
    return service().search(**query.model_dump())


@app.get("/autocomplete", dependencies=[Depends(auth)])
def autocomplete(prefix: str):
    return service().autocomplete(prefix)
