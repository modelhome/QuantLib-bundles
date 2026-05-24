# to build and run from your local machine:
#   docker build -t quantlib-bond:local .
#   docker run --rm quantlib-bond:local                 # uses default bond_spec.json
#   docker run --rm -v "$PWD/run:/run" quantlib-bond:local run/bond_spec.json

FROM python:3.12-slim

WORKDIR /app

# QuantLib ships as a prebuilt wheel (bundles the compiled C++ library), so no
# build toolchain or source compilation is needed. Pin for reproducibility.
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir QuantLib==1.42.1

COPY runner.py bond_spec.json ./

ENTRYPOINT ["python", "runner.py"]

# irl the input/output paths come from the Modelfile; for local testing we
# default to the bundled sample input.
CMD ["bond_spec.json"]
