#!/usr/bin/env python3
"""
Model Home runner: QuantLib fixed-rate bond pricing off a constructed yield curve.

Reads a single JSON input file (positional arg, default ``bond_spec.json``),
prices a fixed-rate bond, and prints a JSON result object to stdout. The
Modelfile redirects stdout to ``run/bond_metrics.output.json``.

Composition hook: if ``climate_risk_premium`` (decimal, e.g. 0.0125) is present
in the input, it is added as a parallel spread to the discount curve. This lets
the model sit downstream of a climate/damage model (e.g. DicePy) as well as run
standalone. Any missing bond parameters fall back to sensible defaults so the
model is composable both ways; a parameter that is present but empty ("" or
null) is treated the same as a missing one.
"""
import sys
import json
import QuantLib as ql


# --- enum maps -------------------------------------------------------------
FREQUENCY = {
    "Annual": ql.Annual,
    "Semiannual": ql.Semiannual,
    "Quarterly": ql.Quarterly,
    "Monthly": ql.Monthly,
}

COMPOUNDING = {
    "Simple": ql.Simple,
    "Compounded": ql.Compounded,
    "Continuous": ql.Continuous,
}

BUSINESS_CONVENTION = {
    "Following": ql.Following,
    "ModifiedFollowing": ql.ModifiedFollowing,
    "Preceding": ql.Preceding,
    "ModifiedPreceding": ql.ModifiedPreceding,
    "Unadjusted": ql.Unadjusted,
}


def day_counter(name):
    name = (name or "Thirty360").lower()
    if name in ("thirty360", "30360", "thirty_360"):
        return ql.Thirty360(ql.Thirty360.BondBasis)
    if name in ("actualactual", "actual_actual", "actact"):
        return ql.ActualActual(ql.ActualActual.Bond)
    if name in ("actual360", "act360"):
        return ql.Actual360()
    if name in ("actual365fixed", "actual365", "act365"):
        return ql.Actual365Fixed()
    raise ValueError("Unknown day_count: %s" % name)


def calendar(name):
    name = (name or "TARGET").lower()
    if name == "target":
        return ql.TARGET()
    if name in ("unitedstates", "us", "usa"):
        return ql.UnitedStates(ql.UnitedStates.GovernmentBond)
    if name in ("unitedkingdom", "uk"):
        return ql.UnitedKingdom()
    return ql.TARGET()


def to_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return ql.Date(d, m, y)


def build_curve(spec, settlement_days, cal, premium):
    """Return a YieldTermStructureHandle from a flat rate or zero-rate nodes,
    optionally shifted by a parallel ``premium`` spread."""
    ctype = spec.get("type") or "flat"
    dc = day_counter(spec.get("day_count") or "Actual365Fixed")

    if ctype == "flat":
        rate = float(spec.get("rate", 0.04))
        base = ql.FlatForward(
            settlement_days, cal, ql.QuoteHandle(ql.SimpleQuote(rate)), dc
        )
    elif ctype == "zero_nodes":
        nodes = spec["nodes"]
        dates = [to_date(n["date"]) for n in nodes]
        rates = [float(n["rate"]) for n in nodes]
        # anchor the curve at the evaluation date if not already included
        eval_date = ql.Settings.instance().evaluationDate
        if dates[0] > eval_date:
            dates.insert(0, eval_date)
            rates.insert(0, rates[0])
        base = ql.ZeroCurve(dates, rates, dc, cal)
    else:
        raise ValueError("Unknown discount_curve.type: %s" % ctype)

    handle = ql.YieldTermStructureHandle(base)
    if premium:
        spread = ql.QuoteHandle(ql.SimpleQuote(float(premium)))
        handle = ql.YieldTermStructureHandle(
            ql.ZeroSpreadedTermStructure(handle, spread)
        )
    return handle


def price(spec):
    # `x.get(k) or default` rather than `x.get(k, default)` throughout: an
    # upstream flow step (or a hand-edited example) can send a key through as ""
    # or null, and a present-but-empty value should fall back the same way a
    # missing one does. Numeric fields deliberately keep `.get(k, default)` --
    # `or` there would rewrite a legitimate 0 into the default.

    # ---- valuation date & conventions ----
    val = spec.get("valuation_date") or "2026-05-24"
    ql.Settings.instance().evaluationDate = to_date(val)

    settlement_days = int(spec.get("settlement_days", 2))
    cal = calendar(spec.get("calendar") or "TARGET")
    biz = BUSINESS_CONVENTION.get(spec.get("business_convention") or "Following",
                                  ql.Following)

    bond_spec = spec.get("bond") or {}
    issue = to_date(bond_spec.get("issue_date") or "2020-06-01")
    maturity = to_date(bond_spec.get("maturity_date") or "2030-06-01")
    coupon = float(bond_spec.get("coupon_rate", 0.05))
    face = float(bond_spec.get("face", 100.0))
    freq = FREQUENCY.get(bond_spec.get("frequency") or "Semiannual", ql.Semiannual)
    dc = day_counter(bond_spec.get("day_count") or "Thirty360")

    # ---- discount curve (+ optional climate spread) ----
    premium = spec.get("climate_risk_premium")
    curve = build_curve(spec.get("discount_curve") or {"type": "flat", "rate": 0.04},
                        settlement_days, cal, premium)

    # ---- build & price the bond ----
    schedule = ql.Schedule(
        issue, maturity, ql.Period(freq), cal, biz, biz,
        ql.DateGeneration.Backward, False,
    )
    bond = ql.FixedRateBond(settlement_days, face, schedule, [coupon], dc)
    bond.setPricingEngine(ql.DiscountingBondEngine(curve))

    clean = bond.cleanPrice()
    dirty = bond.dirtyPrice()
    accrued = bond.accruedAmount()
    ytm = bond.bondYield(dc, ql.Compounded, freq)

    rate = ql.InterestRate(ytm, dc, ql.Compounded, freq)
    mac = ql.BondFunctions.duration(bond, rate, ql.Duration.Macaulay)
    mod = ql.BondFunctions.duration(bond, rate, ql.Duration.Modified)
    convexity = ql.BondFunctions.convexity(bond, rate)
    bpv = ql.BondFunctions.basisPointValue(bond, rate)

    out = {
        "npv": bond.NPV(),
        "clean_price": clean,
        "dirty_price": dirty,
        "accrued_interest": accrued,
        "ytm": ytm,
        "macaulay_duration": mac,
        "modified_duration": mod,
        "convexity": convexity,
        "bpv": bpv,
        "settlement_date": str(bond.settlementDate()),
        "climate_risk_premium_applied": float(premium) if premium else 0.0,
    }
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "bond_spec.json"
    with open(path) as fh:
        spec = json.load(fh)
    result = price(spec)
    # only the JSON result goes to stdout; logs (if any) go to stderr
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
