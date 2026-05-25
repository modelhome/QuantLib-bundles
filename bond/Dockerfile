# to build and run from your local machine (run from the repo root, not from
# bond/ — Model Home's overlay puts the bundle clone at the build-context root,
# so we use repo-relative paths to keep local and on-platform builds in sync):
#   docker build -f bond/Dockerfile -t quantlib-bond:local .
#   docker run --rm quantlib-bond:local                 # uses default bond_spec.json
#   docker run --rm -v "$PWD/run:/run" quantlib-bond:local /run/bond_spec.json

FROM python:3.12-slim

WORKDIR /app

# QuantLib ships as a prebuilt wheel (bundles the compiled C++ library), so no
# build toolchain or source compilation is needed. Pin for reproducibility.
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir QuantLib==1.42.1

COPY bond/runner.py bond/bond_spec.json ./

ENTRYPOINT ["python", "runner.py"]

# irl the input/output paths come from the Modelfile; for local testing we
# default to the bundled sample input.
CMD ["bond_spec.json"]
