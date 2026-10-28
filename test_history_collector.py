import tempfile
import unittest
from pathlib import Path
from lab import history_collector as h


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=h.connect(Path(self.tmp.name)/"history.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_complete_restart_matches_uninterrupted_data(self):
        r=h.run()
        self.assertEqual(r["unique_bars"],39000)
        self.assertEqual(r["pages_after_restart"],377)
        self.assertEqual(r["completed_rerun_requests"],0)
        self.assertTrue(r["matches_uninterrupted_run"])
        self.assertTrue(all(m["bars"]==m["checkpoint"]==390 for m in r["manifest"]))

    def test_boundary_overlap_is_deduplicated(self):
        provider=h.SyntheticProvider()
        r=h.collect(self.db,provider,["SIM001"],lambda _:None)
        self.assertEqual(r["duplicates"],3)
        self.assertEqual(h.manifest(self.db,["SIM001"])[0]["bars"],390)

    def test_conflict_rolls_back_new_rows_and_checkpoint(self):
        p=h.SyntheticProvider()
        rows,n=p.fetch("SIM001",0)
        h.commit_page(self.db,"SIM001",0,rows,n)
        more,n=p.fetch("SIM001",100)
        more[0]["volume"]+=1
        more=more[1:]+more[:1]  # insert new rows before encountering the conflict
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            h.commit_page(self.db,"SIM001",100,more,n)
        self.assertEqual(h.current(self.db,"SIM001"),100)
        self.assertEqual(h.manifest(self.db,["SIM001"])[0]["bars"],100)

    def test_missing_bar_cannot_advance_checkpoint(self):
        rows,n=h.SyntheticProvider().fetch("SIM001",0)
        with self.assertRaisesRegex(ValueError,"missing"):
            h.commit_page(self.db,"SIM001",0,rows[1:],n)
        self.assertEqual(h.current(self.db,"SIM001"),0)
        self.assertEqual(h.manifest(self.db,["SIM001"])[0]["bars"],0)

    def test_retry_after_is_honored_and_retries_are_bounded(self):
        class Failing:
            calls=0
            def fetch(self,symbol,cursor):
                self.calls+=1
                raise h.TransientError(429,3)
        p,delays=Failing(),[]
        with self.assertRaises(h.TransientError):
            h.collect(self.db,p,["SIM001"],delays.append)
        self.assertEqual(p.calls,4)
        self.assertEqual(delays,[3,3,4])
        self.assertEqual(h.current(self.db,"SIM001"),0)

    def test_permanent_error_is_not_retried(self):
        class Failing:
            calls=0
            def fetch(self,symbol,cursor):
                self.calls+=1
                raise h.TransientError(401)
        p=Failing()
        with self.assertRaises(h.TransientError):
            h.collect(self.db,p,["SIM001"],lambda _:None)
        self.assertEqual(p.calls,1)

    def test_cursor_loop_is_rejected(self):
        with self.assertRaises(ValueError):
            h.commit_page(self.db,"SIM001",0,[],0)


if __name__ == "__main__":
    unittest.main()
