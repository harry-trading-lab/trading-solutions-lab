import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from lab import market_audit as audit, execution_gap as gap, paper_router as bot


class DataAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        audit.write_fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def edit_manifest(self, action):
        path = self.root / "manifest.json"
        data = json.loads(path.read_text())
        action(data)
        path.write_text(json.dumps(data))

    def test_clean_fixture_passes_without_mutation(self):
        before = {p.name: audit.digest(p) for p in self.root.glob("*.json")}
        result = audit.audit(self.root)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["expected_bars"], 276)
        self.assertEqual(before, {p.name: audit.digest(p) for p in self.root.glob("*.json")})

    def test_corruption_detects_all_eight_seeded_classes(self):
        audit.write_fixture(self.root, broken=True)
        result = audit.audit(self.root)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(set(result["finding_counts"]), {
            "HASH_MISMATCH", "PAGINATION_GAP", "MISSING_BAR", "DUPLICATE_BAR",
            "CONFLICTING_DUPLICATE", "OUT_OF_SESSION", "UNEXPECTED_SYMBOL", "INVALID_OHLCV"})

    def test_calendar_holiday_and_early_close(self):
        schedule = audit.schedule()
        self.assertEqual(len(schedule["2022-11-23"]), 78)
        self.assertEqual(schedule["2022-11-24"], [])
        self.assertEqual(len(schedule["2022-11-25"]), 42)
        self.assertTrue(schedule["2022-11-25"][-1].startswith("2022-11-25T17:55"))

    def test_dst_changes_utc_open(self):
        schedule = audit.schedule()
        self.assertIn("T14:30", schedule["2022-03-11"][0])
        self.assertIn("T13:30", schedule["2022-03-14"][0])

    def test_2018_exceptional_closure(self):
        self.assertEqual(audit.schedule(["2018-12-05"])["2018-12-05"], [])

    def test_manifest_cannot_escape_input_directory(self):
        self.edit_manifest(lambda m: m["pages"][0].update(file="../outside.json"))
        with self.assertRaises(ValueError):
            audit.audit(self.root)

    def test_duplicate_page_is_flagged(self):
        self.edit_manifest(lambda m: m["pages"].append(dict(m["pages"][0])))
        self.assertIn("DUPLICATE_PAGE", audit.audit(self.root)["finding_counts"])

    def test_unfinished_cursor_chain_is_flagged(self):
        self.edit_manifest(lambda m: m["pages"].pop())
        self.assertIn("INCOMPLETE_PAGINATION", audit.audit(self.root)["finding_counts"])

    def test_equivalent_timezone_is_not_missing(self):
        path = self.root / "page-00.json"
        data = json.loads(path.read_text())
        data["bars"][0]["timestamp"] = "2022-03-11T09:30:00-05:00"
        path.write_text(json.dumps(data))
        self.edit_manifest(lambda m: m["pages"][0].update(sha256=audit.digest(path)))
        self.assertEqual(audit.audit(self.root)["decision"], "PASS")


class AttributionTests(unittest.TestCase):
    def test_fixture_reconciles_exactly(self):
        result = gap.analyze(gap.fixture())
        self.assertEqual(result["totals"], dict(theoretical=620., timing=-160., execution=-48.,
                                               fees=32., net=380., residual=0.))
        self.assertEqual(result["causality_flags"], 1)

    def test_long_and_short_have_correct_signed_costs(self):
        long, short = [gap.reconcile_trade(r) for r in gap.fixture()[:2]]
        self.assertEqual(long["timing"], -20.)
        self.assertEqual(short["timing"], -20.)
        self.assertEqual(long["execution"], -6.)
        self.assertEqual(short["execution"], -6.)

    def test_zero_cost_fills_equal_theoretical(self):
        row = gap.fixture()[0]
        row.update(entry_fill_mid=row["entry_signal_mid"], exit_fill_mid=row["exit_signal_mid"],
                   entry_fill=row["entry_signal_mid"], exit_fill=row["exit_signal_mid"], fees=0)
        result = gap.reconcile_trade(row)
        self.assertEqual(result["theoretical"], result["net"])

    def test_future_feature_is_flagged(self):
        self.assertIn("FEATURE_AFTER_SIGNAL", gap.reconcile_trade(gap.fixture()[2])["findings"])

    def test_fill_before_signal_is_flagged(self):
        row = gap.fixture()[0]
        row["entry_filled_at"] = "2022-11-23T14:29:00+00:00"
        self.assertIn("NON_CAUSAL_FILL_TIMELINE", gap.reconcile_trade(row)["findings"])

    def test_duplicate_trade_ids_rejected(self):
        row = gap.fixture()[0]
        with self.assertRaises(ValueError):
            gap.analyze([row, row])

    def test_invalid_numeric_inputs_rejected(self):
        for field, value in [("quantity", 0), ("entry_fill", "NaN"), ("fees", -1)]:
            row = gap.fixture()[0]
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                gap.reconcile_trade(row)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "router.db"
        self.venues = [bot.PaperVenue("A"), bot.PaperVenue("B")]
        self.router = bot.Router(self.path, self.venues)
        self.signal = bot.Signal("candle-1", 1000, 100., 2)

    def tearDown(self):
        self.router.close()
        self.tmp.cleanup()

    def test_duplicate_signal_submits_once_per_account(self):
        self.router.dispatch(self.signal, 1000)
        self.router.dispatch(self.signal, 1000)
        self.assertEqual([v.submissions for v in self.venues], [1, 1])

    def test_changed_intent_with_same_key_is_held(self):
        self.router.dispatch(self.signal, 1000)
        result = self.router.dispatch(replace(self.signal, target=1), 1000)
        self.assertEqual(set(result.values()), {"HELD"})
        self.assertEqual([v.submissions for v in self.venues], [1, 1])

    def test_disconnect_isolated_and_recovery_catches_up(self):
        self.venues[0].connected = False
        result = self.router.dispatch(self.signal, 1000)
        self.assertEqual(result, {"A": "HELD", "B": "FILLED"})
        self.venues[0].connected = True
        self.router.dispatch(self.signal, 1000)
        self.assertEqual([v.position for v in self.venues], [2, 2])

    def test_ack_loss_recovers_after_restart(self):
        self.venues[0].lose_ack_once = True
        self.router.dispatch(self.signal, 1000)
        self.router.close()
        self.router = bot.Router(self.path, self.venues)
        self.router.dispatch(self.signal, 1000)
        self.assertEqual(self.router.ledger_position("A"), 2)
        self.assertEqual(self.venues[0].submissions, 1)

    def test_unclosed_stale_and_excess_position_block_all(self):
        for signal in [replace(self.signal, closed_at=1001), replace(self.signal, closed_at=800),
                       replace(self.signal, target=3), replace(self.signal, price=float("nan"))]:
            with self.subTest(signal=signal), self.assertRaises(ValueError):
                self.router.dispatch(signal, 1000)
        self.assertEqual([v.submissions for v in self.venues], [0, 0])

    def test_disabled_account_is_not_touched(self):
        self.venues[0].enabled = False
        result = self.router.dispatch(self.signal, 1000)
        self.assertEqual(result["A"], "DISABLED")
        self.assertEqual(self.venues[0].submissions, 0)

    def test_rejection_does_not_change_position(self):
        self.venues[0].reject_next = True
        result = self.router.dispatch(self.signal, 1000)
        self.assertEqual(result["A"], "REJECTED")
        self.assertEqual(self.venues[0].position, 0)
        self.router.dispatch(self.signal, 1000)
        self.assertEqual(self.venues[0].submissions, 1)

    def test_flat_signal_closes_position(self):
        self.router.dispatch(self.signal, 1000)
        self.router.dispatch(bot.Signal("candle-2", 1060, 101., 0), 1060)
        self.assertEqual([v.position for v in self.venues], [0, 0])

    def test_position_mismatch_isolated(self):
        self.venues[0].position = 1
        result = self.router.dispatch(self.signal, 1000)
        self.assertEqual(result, {"A": "HELD", "B": "FILLED"})

    def test_unknown_pending_intent_never_blindly_resubmits(self):
        with self.router.db:
            self.router.db.execute("INSERT INTO intents VALUES ('unknown','A','old',2,100,2,'PENDING')")
        result = self.router.dispatch(self.signal, 1000)
        self.assertEqual(result["A"], "HELD")
        self.assertEqual(self.venues[0].submissions, 0)

    def test_strategy_is_prefix_invariant(self):
        bars = bot.candles()
        full = bot.signals(bars)
        for size in [10, 20, 40]:
            prefix = bot.signals(bars[:size])
            self.assertEqual(prefix, [s for s in full if s.closed_at <= bars[size-1]["closed_at"]])

    def test_trailing_exit_uses_only_closed_prices(self):
        prices = [100.] * 7 + [101., 104., 102.]
        bars = [{"closed_at": 1000 + i * 60, "close": p} for i, p in enumerate(prices)]
        result = bot.signals(bars)
        self.assertEqual(result[0].target, 2)
        self.assertEqual(result[-1].target, 0)
        self.assertIn("trailing", result[-1].reason)

    def test_full_demo_has_no_duplicate_orders(self):
        result = bot.run()
        self.assertEqual(result["account_count"], 7)
        self.assertEqual(result["duplicate_submissions"], 0)
        self.assertGreater(result["event_counts"]["RECOVERED"], 0)
        self.assertTrue(all(a["position"] == a["ledger_position"] for a in result["accounts"]))


if __name__ == "__main__":
    unittest.main()
