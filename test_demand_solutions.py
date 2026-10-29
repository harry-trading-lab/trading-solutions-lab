import copy
import json
import math
import random
import unittest
from decimal import Decimal, localcontext

from solutions.vwap.core import RangeVWAP
from solutions.analysis_review.core import review, holm, instant
from solutions.calculation_boundary.engine.server import calculate
from solutions.calculation_boundary.harness import running_services, post


def oracle(bars):
    with localcontext() as ctx:
        ctx.prec = 50
        rows = [(Decimal(str(p)), Decimal(str(v))) for p, v in bars]
        total = sum((v for _, v in rows), Decimal(0))
        if not total:
            return None, None
        mean = sum((p * v for p, v in rows), Decimal(0)) / total
        variance = sum((v * (p - mean) ** 2 for p, v in rows), Decimal(0)) / total
        return float(mean), float(variance)


def clean_manifest():
    return {
        "rows": [
            {
                "sample_id": "a",
                "split": "train",
                "decision_at": "2026-01-01T10:00:00Z",
                "feature_available_at": "2026-01-01T10:00:00Z",
                "label_end_at": "2026-01-02T10:00:00Z",
            },
            {
                "sample_id": "b",
                "split": "test",
                "decision_at": "2026-01-03T10:00:00Z",
                "feature_available_at": "2026-01-03T09:00:00Z",
                "label_end_at": "2026-01-04T10:00:00Z",
            },
        ],
        "preprocessing_fit_ids": ["a"],
        "pvalues": {"baseline": 0.3},
        "claim": {"kind": "predictive", "design": "observational"},
    }


class TestVWAP(unittest.TestCase):
    def test_hand_calculation(self):
        r = RangeVWAP([(10, 1), (20, 3)]).query(0, 2)
        self.assertEqual(r.mean, 17.5)
        self.assertEqual(r.variance, 18.75)

    def test_random_ranges_against_decimal_oracle(self):
        rng = random.Random(49)
        bars = [
            (round(rng.uniform(50, 500), 4), rng.randrange(1000)) for _ in range(129)
        ]
        tree = RangeVWAP(bars)
        for _ in range(80):
            start = rng.randrange(len(bars))
            stop = rng.randrange(start + 1, len(bars) + 1)
            expected, variance = oracle(bars[start:stop])
            result = tree.query(start, stop)
            self.assertAlmostEqual(result.mean, expected, places=10)
            self.assertAlmostEqual(result.variance, variance, places=7)

    def test_large_offset_small_dispersion(self):
        bars = [(1e9 + i * 0.001, i + 1) for i in range(20)]
        tree = RangeVWAP(bars)
        for start in [0, 3, 10, 19]:
            mean, var = oracle(bars[start:])
            r = tree.query(start, len(bars))
            self.assertAlmostEqual(r.mean, mean, delta=5e-7)
            self.assertAlmostEqual(r.variance, var, delta=2e-9)

    def test_revision_invalidates_ranges(self):
        bars = [(10, 2), (20, 1), (30, 3)]
        tree = RangeVWAP(bars)
        tree.revise(1, 100, 4)
        bars[1] = (100, 4)
        for start, stop in [(0, 3), (1, 3), (0, 1)]:
            mean, var = oracle(bars[start:stop])
            r = tree.query(start, stop)
            self.assertAlmostEqual(r.mean, mean)
            self.assertAlmostEqual(r.variance, var)

    def test_invalid_revision_does_not_mutate(self):
        tree = RangeVWAP([(10, 2), (20, 3)])
        before = tree.query(0, 2)
        with self.assertRaises(ValueError):
            tree.revise(0, 99, -1)
        self.assertEqual(before, tree.query(0, 2))

    def test_empty_and_zero_weight(self):
        self.assertIsNone(RangeVWAP([]).query(0, 0).variance)
        self.assertIsNone(RangeVWAP([(10, 0)]).query(0, 1).result()["vwap"])
        self.assertEqual(RangeVWAP([(10, 0), (30, 2)]).query(0, 2).mean, 30)

    def test_validation_and_ranges(self):
        for p, v in [(math.nan, 1), (1, math.inf), (1, -1), (True, 2), (1e13, 1)]:
            with self.assertRaises(ValueError):
                RangeVWAP([(p, v)])
        t = RangeVWAP([(1, 1)])
        for a, b in [(-1, 1), (0, 2), (1, 0), (False, 1), (0.0, 1)]:
            with self.assertRaises(ValueError):
                t.query(a, b)

    def test_symbol_isolation(self):
        a = RangeVWAP([(10, 1)])
        b = RangeVWAP([(100, 1)])
        a.revise(0, 20, 1)
        self.assertEqual(b.query(0, 1).mean, 100)


class TestAnalysisReview(unittest.TestCase):
    def test_clean_control_and_no_mutation(self):
        spec = clean_manifest()
        original = copy.deepcopy(spec)
        self.assertEqual(review(spec)["status"], "NO_FLAGS_IN_DECLARED_CHECKS")
        self.assertEqual(spec, original)

    def test_feature_availability(self):
        spec = clean_manifest()
        spec["rows"][1]["feature_available_at"] = "2026-01-03T10:00:01Z"
        self.assertIn(
            "FEATURE_UNAVAILABLE_AT_DECISION",
            {f["code"] for f in review(spec)["findings"]},
        )

    def test_label_crossing_and_equality(self):
        for stamp in ["2026-01-03T10:00:00Z", "2026-01-04T10:00:00Z"]:
            spec = clean_manifest()
            spec["rows"][0]["label_end_at"] = stamp
            self.assertIn(
                "TRAIN_LABEL_OVERLAPS_TEST",
                {f["code"] for f in review(spec)["findings"]},
            )

    def test_reused_identity_and_scaler_leak(self):
        spec = clean_manifest()
        spec["rows"][1]["sample_id"] = "a"
        codes = {f["code"] for f in review(spec)["findings"]}
        self.assertIn("SAMPLE_ID_REUSED", codes)
        self.assertIn("PREPROCESSING_FIT_OUTSIDE_TRAIN", codes)

    def test_unknown_fit_id(self):
        spec = clean_manifest()
        spec["preprocessing_fit_ids"] = ["unknown"]
        self.assertEqual(
            review(spec)["findings"][0]["code"], "PREPROCESSING_FIT_OUTSIDE_TRAIN"
        )

    def test_causal_claim_requires_review(self):
        spec = clean_manifest()
        spec["claim"]["kind"] = "causal"
        self.assertIn(
            "CAUSAL_CLAIM_REQUIRES_IDENTIFICATION_REVIEW",
            {f["code"] for f in review(spec)["findings"]},
        )

    def test_holm_known_values_and_order_independence(self):
        expected = {"a": 0.03, "b": 0.06, "c": 0.06}
        for inp in [
            {"a": 0.01, "b": 0.03, "c": 0.04},
            {"c": 0.04, "a": 0.01, "b": 0.03},
        ]:
            result = holm(inp)
            self.assertEqual({k: v["adjusted_p"] for k, v in result.items()}, expected)
            self.assertEqual(
                [k for k, v in result.items() if v["reject_at_alpha"]], ["a"]
            )

    def test_schema_and_nonfinite_rejected(self):
        for value in [True, math.nan, math.inf, -0.01, 1.1, "0.01"]:
            with self.assertRaises(ValueError):
                holm({"p": value})
        with self.assertRaises(ValueError):
            instant("2026-01-01")
        spec = clean_manifest()
        spec["rows"][0]["split"] = "other"
        with self.assertRaises(ValueError):
            review(spec)

    def test_timezone_equivalence(self):
        self.assertEqual(
            instant("2026-01-01T10:00:00Z"), instant("2026-01-01T05:00:00-05:00")
        )


class TestCalculationBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = running_services()
        cls.s = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_placeholder_decimal_result(self):
        self.assertEqual(
            calculate({"principal_cents": 10000, "annual_rate_bps": 1000, "years": 2})[
                "future_value_cents"
            ],
            12100,
        )

    def test_engine_bounds(self):
        for data in [
            {"principal_cents": True, "annual_rate_bps": 0, "years": 1},
            {"principal_cents": -1, "annual_rate_bps": 0, "years": 1},
            {"principal_cents": 1, "annual_rate_bps": 0, "years": 51},
            {},
        ]:
            with self.assertRaises(ValueError):
                calculate(data)

    def test_developer_fixture_allowed_live_forbidden(self):
        s = self.s
        self.assertEqual(post(s["public"], "/v1/mock", s["developer"])[0], 200)
        self.assertEqual(post(s["public"], "/v1/quote", s["developer"])[0], 403)

    def test_application_live_route_and_direct_engine_denial(self):
        s = self.s
        data = {"principal_cents": 10000, "annual_rate_bps": 1000, "years": 2}
        code, result = post(s["public"], "/v1/quote", s["application"], data)
        self.assertEqual((code, result["future_value_cents"]), (200, 12100))
        self.assertEqual(
            post(s["private"], "/calculate", s["application"], data)[0], 401
        )
        self.assertEqual(post(s["private"], "/calculate", s["developer"], data)[0], 401)

    def test_anonymous_and_unknown_path(self):
        s = self.s
        self.assertEqual(post(s["public"], "/v1/quote")[0], 401)
        self.assertEqual(post(s["public"], "/source", s["application"])[0], 404)

    def test_malformed_large_and_extra_fields(self):
        s = self.s
        self.assertEqual(
            post(s["public"], "/v1/quote", s["application"], raw=b"{")[0], 400
        )
        self.assertEqual(
            post(s["public"], "/v1/quote", s["application"], raw=b"x" * 5000)[0], 413
        )
        self.assertEqual(
            post(s["public"], "/v1/quote", s["application"], {"extra": 1})[0], 400
        )

    def test_audit_does_not_expose_tokens_or_payload(self):
        s = self.s
        post(
            s["public"],
            "/v1/quote",
            s["application"],
            {"secret_payload": "sensitive-value"},
        )
        log = s["audit"].read_text()
        for secret in [
            s["service"],
            s["developer"],
            s["application"],
            "secret_payload",
            "sensitive-value",
        ]:
            self.assertNotIn(secret, log)
        self.assertTrue(
            all(
                set(json.loads(line)) == {"role", "route", "status"}
                for line in log.splitlines()
            )
        )

    def test_z_engine_failure_fails_closed_mock_survives(self):
        s = self.s
        s["engine"].terminate()
        s["engine"].wait(timeout=5)
        self.assertEqual(post(s["public"], "/v1/quote", s["application"], {})[0], 502)
        self.assertEqual(post(s["public"], "/v1/mock", s["developer"])[0], 200)


if __name__ == "__main__":
    unittest.main()
