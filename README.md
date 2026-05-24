# QuantLib-bundles

Standalone [Model Home](https://modelhome.run) model bundles built on
[QuantLib](https://www.quantlib.org/). Each subfolder is a self-contained model:
a `Modelfile.toml`, a `Dockerfile`, a `runner.py`, and sample inputs.

This is not a fork of QuantLib — QuantLib is installed as a pinned pip wheel
inside each bundle's image.

## Bundles

| Bundle | Model | Inputs → Outputs |
|---|---|---|
| [`bond/`](./bond) | Fixed-rate bond pricing off a constructed discount curve | bond + curve spec → price, yield, duration, convexity, BPV |

## Quick start

```bash
cd bond
docker build -t quantlib-bond:local .
docker run --rm quantlib-bond:local
```

Or run the runner directly:

```bash
pip install QuantLib==1.42.1
python bond/runner.py bond/bond_spec.json
```

See [`CLAUDE.md`](./CLAUDE.md) for the full design notes, the Modelfile format,
verified results, and the project task list.
