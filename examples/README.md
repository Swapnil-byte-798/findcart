# Reproducible historical catalogue

`uci_catalogue.json.gz` contains 3,898 derived products. Import it from the repository root:

```bash
python -m findcart import-json examples/uci_catalogue.json.gz
```

Then send `/search` a query such as `{"query":"red bag under 5","currency":"GBP"}`. The CLI demo uses three clearly labelled authored products instead of this dataset.

Source: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Dataset page: https://archive.ics.uci.edu/dataset/352/online+retail. Licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

Changes: retain the latest eligible positive-price, positive-quantity, non-cancelled transaction for each physical product code; sum eligible quantities for historical popularity; extract colour only when the literal word appears in its description; omit customer identifiers and invoice-level details. Prices are GBP from 2010–2011, not current offers. No endorsement by the original author is implied.

For reproduction, download the official ZIP to any local path, install `openpyxl>=3.1`, and run `python examples/prepare_retail.py /path/to/online-retail.zip`. The script replaces the derived catalogue and provenance metadata, not application data. Archive checksum and row counts are recorded in `evidence/data_source.json`.
