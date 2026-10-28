import unittest
from copy import deepcopy
from lab import order_repeat as orders, strategy_trial as research


class OrderPlanTests(unittest.TestCase):
    def test_four_repeats_mean_five_independent_pairs(self):
        result = orders.plan()
        self.assertEqual((result["groups"], result["order_count"], result["total_entry_shares"]), (5, 10, 50))
        self.assertEqual(result["stop_distance_exposure"], "100.00")
        self.assertEqual(len({r["orderId"] for r in result["orders"]}), 10)
        for parent, child in zip(result["orders"][::2], result["orders"][1::2]):
            self.assertEqual(child["parentId"], parent["orderId"])
            self.assertEqual(parent["parentId"], 0)
            self.assertEqual(child["totalQuantity"], parent["totalQuantity"])
            self.assertFalse(parent["transmit"] or child["transmit"])

    def test_short_uses_buy_stop_above_entry(self):
        result = orders.plan(side="SELL", stop="102", repeats=0)
        self.assertEqual(result["order_count"], 2)
        self.assertEqual(result["orders"][1]["action"], "BUY")

    def test_rejects_wrong_side_and_inexact_tick(self):
        for kwargs in ({"stop": "101"}, {"side": "SELL", "stop": "99"},
                       {"entry": "100.001"}, {"stop": "NaN"}, {"tick": "Infinity"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                orders.plan(**kwargs)

    def test_rejects_aggregate_exposure_not_just_one_group(self):
        with self.assertRaisesRegex(ValueError, "Aggregate"):
            orders.plan(quantity=30, repeats=4, max_shares=100)

    def test_invalid_counts_and_ids(self):
        for kwargs in ({"repeats": -1}, {"repeats": True}, {"repeats": 1.5},
                       {"quantity": 0}, {"first_id": 2147483646}, {"repeats": 100}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                orders.plan(**kwargs)


class ResearchTests(unittest.TestCase):
    def test_future_mutation_cannot_change_training_selection(self):
        bars = research.fixture()
        expected = research.choose(bars, 240)
        changed = deepcopy(bars)
        for row in changed[240:]:
            row["open"] *= 10
            row["close"] *= 20
        self.assertEqual(research.choose(changed, 240), expected)

    def test_signal_does_not_use_current_or_future_close(self):
        bars = research.fixture()
        result = research.signal(bars, 240, 20)
        bars[240]["close"] = 1000000
        self.assertEqual(research.signal(bars, 240, 20), result)
        self.assertEqual(research.signal(bars[:240], 240, 20), result)

    def test_round_trip_fees_and_known_price_change(self):
        bars = [{"day": i, "open": p, "close": p} for i, p in enumerate([100, 110, 121])]
        r = research.evaluate(bars, 0, 2, 2, cost_bps=10, buy_hold=True)
        self.assertAlmostEqual(r["net_return"], 1.099**2-1)
        self.assertEqual(r["turnover"], 2)
        self.assertAlmostEqual(sum(t["cost"] for t in r["trace"]), .002)

    def test_flat_market_pays_both_sides(self):
        bars = [{"day": i, "open": 100, "close": 100} for i in range(3)]
        r = research.evaluate(bars, 0, 1, 2, cost_bps=5, buy_hold=True)
        self.assertAlmostEqual(r["net_return"], -.001)

    def test_folds_cover_240_unique_observations_and_reconcile(self):
        r = research.run()
        days = [t["day"] for f in r["folds"] for t in f["test"]["trace"]]
        self.assertEqual(days, list(range(240, 480)))
        wealth = 1.0
        for fold in r["folds"]:
            self.assertLess(fold["last_training_mark"], fold["test_start"])
            best = max(fold["training_candidates"], key=lambda s: (s["net_return"], -s["lookback"]))
            self.assertEqual(best["lookback"], fold["selected_lookback"])
            self.assertLessEqual(fold["double_cost_net_return"], fold["test"]["net_return"])
            for row in fold["test"]["trace"]:
                self.assertLess(row["feature_last_day"], row["day"])
                self.assertAlmostEqual(row["net"], row["gross"]-row["cost"])
                wealth *= 1+row["net"]
        self.assertAlmostEqual(wealth-1, r["net_return"])

    def test_invalid_data_fails(self):
        for price in (0, -1, float("nan"), float("inf")):
            bars = research.fixture()
            bars[5]["open"] = price
            with self.assertRaises(ValueError):
                research.run(bars)


if __name__ == "__main__":
    unittest.main()
