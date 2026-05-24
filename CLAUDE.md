# QuantLib-bundles

Standalone Model Home **model bundles** that wrap [QuantLib](https://www.quantlib.org/)
computations. Each bundle is a self-contained folder with everything Model Home
needs to run one model: a `Modelfile.toml`, a `Dockerfile`, a `runner.py`, and
sample input(s).

This repo is **not** a fork of QuantLib. QuantLib is pulled in as a pinned pip
wheel inside each bundle's Docker image, so the repo stays small and only holds
the Model Home packaging layer.

```
QuantLib-bundles/
  CLAUDE.md                 ← you are here
  README.md
  bond/                     ← first bundle: fixed-rate bond pricing
    Modelfile.toml
    Dockerfile
    runner.py
    bond_spec.json                  (default / standalone sample input)
    bond_spec.curve_example.json    (zero-curve + climate-spread sample)
  <future bundles>/         ← e.g. swap/, option/  (same shape, one image each)
```

---

## What Model Home is (context for this repo)

Model Home is a platform for discovering, running, and composing computational
models. A model is added by pointing the platform at a repo that contains:

- a **`Modelfile.toml`** — an open standard describing how the model runs: its
  container image, the `run` command, and typed `[[inputs]]` / `[[outputs]]`
  (JSON-schema style). It also defines composition — how one model's output
  becomes another's input.
- a **`Dockerfile`** — builds the image the `Modelfile` references.
- a **runner** — reads input JSON file(s) passed as positional args and prints
  the result JSON to **stdout**; the platform's `run` command redirects stdout
  to `run/<output_name>.output.json`.

### Modelfile format (as used by the existing FinancePy model)

```toml
name = "model_name"
run  = "docker run --rm -v \"$PWD/run:/run\" ${IMAGE} ${ARGS} > run/<output>.output.json"
image = "modelhome/<image>:latest"
args  = ["{input:<input_name>}"]      # {input:NAME} / {output:NAME} placeholders

[resources]
memory = "1Gi"
cpu = "1"

[[inputs]]
name = "<input_name>"
[inputs.schema]
type = "object"
required = []                          # [] keeps the model composable downstream

[[outputs]]
name = "<output_name>"
[outputs.schema]
type = "object"
required = ["..."]
properties.<field>.type = "number"
```

Reference example (the existing bond pricer built on FinancePy):
`https://raw.githubusercontent.com/modelhome/FinancePy/HEAD/Modelfile.toml`

---

## The `bond/` bundle

Prices a **fixed-rate bond off a constructed discount curve** using QuantLib.
It deliberately leans on QuantLib's curve machinery so it adds value beyond the
existing FinancePy bond pricer (which uses a flat curve).

### Input (`bond_spec`, one JSON object)

`required = []` on purpose — the runner supplies defaults for any missing field,
so the model runs **standalone** (full spec via file) **or composed** (only a
spread present, bond params defaulted). Shape:

| field | type | notes |
|---|---|---|
| `valuation_date` | ISO date | default `2026-05-24` |
| `settlement_days` | int | default 2 |
| `calendar` | str | `TARGET` \| `UnitedStates` \| `UnitedKingdom` |
| `business_convention` | str | `Following` \| `ModifiedFollowing` \| `Unadjusted` \| … |
| `bond.issue_date` / `bond.maturity_date` | ISO date | |
| `bond.coupon_rate` | decimal | e.g. `0.05` |
| `bond.frequency` | str | `Annual` \| `Semiannual` \| `Quarterly` \| `Monthly` |
| `bond.face` | number | default 100 |
| `bond.day_count` | str | `Thirty360` \| `ActualActual` \| `Actual360` \| `Actual365Fixed` |
| `discount_curve.type` | str | `flat` `{rate}` or `zero_nodes` `{nodes:[{date,rate}]}` |
| `climate_risk_premium` | decimal | optional; see composition hook below |

### Output (`bond_metrics`)

`npv`, `clean_price`, `dirty_price`, `accrued_interest`, `ytm`,
`macaulay_duration`, `modified_duration`, `convexity`, `bpv`,
`settlement_date`, `climate_risk_premium_applied`.

### Composition hook

If `climate_risk_premium` (decimal, e.g. `0.0125`) is present, it is applied as
a parallel spread to the discount curve (`ZeroSpreadedTermStructure`). This lets
the bond bundle sit **downstream of a climate/damage model** (e.g. DicePy) in the
climate → risk → finance chain, the same way the FinancePy model does. Drop the
field to keep it purely standalone.

### Verified results (runner tested directly, QuantLib 1.42.1)

- `bond_spec.json` (5% coupon, ~4y, flat 4% curve) → clean price **103.51**,
  ytm **4.05%**, modified duration **3.54**.
- `bond_spec.curve_example.json` (4.5% coupon, zero curve + 125bp climate
  spread) → ytm **5.77%**, clean price **92.27**.

### Build & run locally

Build context is the **bundle subfolder**:

```bash
cd bond
docker build -t quantlib-bond:local .
docker run --rm quantlib-bond:local                      # uses default bond_spec.json
# or with mounted run dir, matching the Modelfile:
mkdir -p run && cp bond_spec.json run/
docker run --rm -v "$PWD/run:/run" quantlib-bond:local run/bond_spec.json > run/bond_metrics.output.json
```

Run the runner without Docker (for quick iteration):

```bash
pip install QuantLib==1.42.1
python bond/runner.py bond/bond_spec.json
```

---

## Open decisions (flagged, not yet resolved)

- **`macaulay_duration` spelling.** This bundle uses the correct spelling. The
  existing FinancePy model outputs `macauley_duration` (missing an 'a'). If the
  catalog should use consistent keys, decide whether to fix FinancePy or match
  its typo here. Currently: correct spelling kept here.
- **Image build/push.** Resolved: Model Home builds the image itself from the
  bundle's Dockerfile and pushes it to the platform registry under a
  deterministic `<upstream-sha>-<bundle-sha>` tag. No manual Docker Hub push
  needed unless we want `modelhome/quantlib-bond:latest` to be independently
  pullable off-platform.
- **Curve bootstrapping.** The curve is currently flat or zero-node interpolated.
  Bootstrapping from market deposit/swap quotes (QuantLib's real strength) is a
  natural next extension, not yet built.

---

## Task list (what to do next in Claude Code)

1. **Init git** in this folder and make an initial commit.
2. **Create a new GitHub repo** named `QuantLib-bundles` (new repo, *not* a fork)
   and push. Confirm with John whether it lives under the `modelhome` org or his
   personal account.
3. **Register the bond bundle with Model Home.** The platform builds and tags
   the image itself via BuildKit on registration (deterministic
   `<upstream-sha>-<bundle-sha>` tag, pushed to the platform registry). The
   `image` field in `Modelfile.toml` is a template variable substituted into
   the `run` command (`${IMAGE}`), not a pull target — no manual `docker push`
   is required for Model Home to run this bundle. (Independently publishing
   `modelhome/quantlib-bond:latest` for off-platform `docker run` use would
   be a separate decision.)
4. **Add the bond model to Model Home** and run it end-to-end against the platform
   — both standalone (`bond_spec.json`) and via the composition hook — to confirm
   the Modelfile, image, and runner all wire up correctly.
5. Only after the bond bundle works on-platform, consider sibling bundles
   (`swap/`, `option/`) and/or curve bootstrapping.

Keep John in the loop on the registry target and the GitHub org/account before
any push.
