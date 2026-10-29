import math
from datetime import datetime


def instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamps must be ISO-8601 strings")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp needs timezone")
    return result


def holm(pvalues, alpha=0.05):
    """Holm step-down FWER adjustment; caller must supply the full test family."""
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not 0 < alpha < 1
    ):
        raise ValueError("invalid alpha")
    if not isinstance(pvalues, dict):
        raise ValueError("pvalues must be an object")
    for key, p in pvalues.items():
        if not isinstance(key, str) or not key:
            raise ValueError("test name required")
        if (
            isinstance(p, bool)
            or not isinstance(p, (int, float))
            or not math.isfinite(p)
            or not 0 <= p <= 1
        ):
            raise ValueError("pvalue must be finite and between 0 and 1")
    ordered = sorted(pvalues, key=lambda k: (pvalues[k], k))
    previous = 0.0
    output = {}
    for i, name in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - i) * pvalues[name]))
        output[name] = {
            "raw_p": pvalues[name],
            "adjusted_p": previous,
            "reject_at_alpha": previous <= alpha,
        }
    return output


def review(spec):
    """Manifest checks: availability, split identity, labels and preprocessing.

    Temporal policy is deliberately explicit: training labels/preprocessing must
    precede the earliest test decision strictly. Equality is conservatively held.
    """
    if not isinstance(spec, dict) or set(spec) != {
        "rows",
        "preprocessing_fit_ids",
        "pvalues",
        "claim",
    }:
        raise ValueError("expected rows, preprocessing_fit_ids, pvalues, claim")
    if not isinstance(spec["rows"], list) or not spec["rows"]:
        raise ValueError("nonempty rows required")
    rows = []
    findings = []
    required = {
        "sample_id",
        "split",
        "decision_at",
        "feature_available_at",
        "label_end_at",
    }
    for idx, row in enumerate(spec["rows"]):
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("invalid row schema")
        if (
            not isinstance(row["sample_id"], str)
            or not row["sample_id"]
            or row["split"] not in ("train", "test")
        ):
            raise ValueError("invalid id/split")
        decision, available, label = (
            instant(row[k])
            for k in ("decision_at", "feature_available_at", "label_end_at")
        )
        if label < decision:
            raise ValueError("label ends before decision")
        rows.append((row, decision, available, label))
        if available > decision:
            findings.append(
                {
                    "code": "FEATURE_UNAVAILABLE_AT_DECISION",
                    "row": idx,
                    "sample_id": row["sample_id"],
                }
            )
    training = [r for r in rows if r[0]["split"] == "train"]
    testing = [r for r in rows if r[0]["split"] == "test"]
    if not training or not testing:
        raise ValueError("both training and test rows required")
    cutoff = min(r[1] for r in testing)
    ids = {}
    for idx, (row, decision, available, label) in enumerate(rows):
        ids.setdefault(row["sample_id"], []).append(row["split"])
        if row["split"] == "train" and (decision >= cutoff or label >= cutoff):
            findings.append(
                {
                    "code": "TRAIN_LABEL_OVERLAPS_TEST",
                    "row": idx,
                    "sample_id": row["sample_id"],
                }
            )
    for name, splits in ids.items():
        if len(splits) > 1:
            findings.append(
                {"code": "SAMPLE_ID_REUSED", "sample_id": name, "splits": splits}
            )
    fit = spec["preprocessing_fit_ids"]
    if not isinstance(fit, list) or any(not isinstance(x, str) for x in fit):
        raise ValueError("fit ids must be a list of strings")
    if len(set(fit)) != len(fit):
        raise ValueError("fit ids must be unique")
    train_ids = {r[0]["sample_id"] for r in training}
    test_ids = {r[0]["sample_id"] for r in testing}
    for name in fit:
        if name not in train_ids or name in test_ids:
            findings.append(
                {"code": "PREPROCESSING_FIT_OUTSIDE_TRAIN", "sample_id": name}
            )
    claim = spec["claim"]
    if not isinstance(claim, dict) or set(claim) != {"kind", "design"}:
        raise ValueError("claim needs kind and design")
    if claim["kind"] not in ("descriptive", "predictive", "causal") or claim[
        "design"
    ] not in ("observational", "randomized"):
        raise ValueError("unknown claim/design")
    if claim["kind"] == "causal" and claim["design"] == "observational":
        findings.append({"code": "CAUSAL_CLAIM_REQUIRES_IDENTIFICATION_REVIEW"})
    adjusted = holm(spec["pvalues"])
    for name, result in adjusted.items():
        if result["raw_p"] <= 0.05 and not result["reject_at_alpha"]:
            findings.append(
                {"code": "SIGNIFICANCE_NOT_RETAINED_AFTER_HOLM", "test": name}
            )
    return {
        "status": "REVIEW_REQUIRED" if findings else "NO_FLAGS_IN_DECLARED_CHECKS",
        "findings": findings,
        "holm": adjusted,
        "rows_checked": len(rows),
        "limitation": "Manifest evidence only. Does not execute notebooks, detect undisclosed trials, or certify causal identification/model validity.",
    }
