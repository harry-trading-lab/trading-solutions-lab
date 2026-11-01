import tempfile
import unittest
from pathlib import Path
import pandas as pd
from rebuild_score_states import parse_game, rebuild


def frame(scores):
    return pd.DataFrame([dict(gameId='001', actionNumber=i+1, period=1,
                              clock=f'PT11M{50-i:02d}.00S', scoreHome=h, scoreAway=a)
                         for i,(h,a) in enumerate(scores)])


class ReplayTests(unittest.TestCase):
    def test_zero_home_score_is_a_valid_pair(self):
        states = parse_game(frame([('0','2'),('0','4'),('2','4')]), '001')
        self.assertEqual([(r['home_score'],r['away_score']) for r in states], [(0,0),(0,2),(0,4),(2,4)])

    def test_trailing_blank_keeps_last_score(self):
        states = parse_game(frame([('2','3'),('',''),(None,None)]), '001')
        self.assertEqual((states[-1]['home_score'],states[-1]['away_score']), (2,3))

    def test_score_decrease_retained_and_flagged(self):
        states = parse_game(frame([('3','0'),('2','0'),('4','0')]), '001')
        self.assertEqual([s['home_score'] for s in states], [0,3,2,4])
        self.assertEqual([s['source_row'] for s in states], [-1,0,1,2])
        self.assertEqual(sum(s['score_decrease'] for s in states), 1)

    def test_malformed_values_rejected(self):
        for pairs in [[('','2')],[('2.5','2')],[('-1','2')],[('nan','2')],[('','')]]:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                parse_game(frame(pairs), '001')
        for field,value in [('clock','PT12M01.00S'),('period',0),('gameId','wrong')]:
            f=frame([('2','0')]); f.loc[0,field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):parse_game(f,'001')

    def test_every_file_accounted_for_with_separate_review_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'; raw.mkdir()
            frame([('0','2')]).to_parquet(raw/'001.parquet',index=False)
            f=frame([('3','0'),('2','0')]);f['gameId']='002';f.to_parquet(raw/'002.parquet',index=False)
            (raw/'003.parquet').write_bytes(b'invalid parquet')
            out=Path(tmp)/'result'; result=rebuild(raw,out)
            self.assertEqual(result['status_counts'], {'accepted':1,'needs_review':1,'rejected':1})
            self.assertEqual(set(pd.read_parquet(out/'accepted.parquet').game_id), {'001'})
            self.assertEqual(set(pd.read_parquet(out/'needs_review.parquet').game_id), {'002'})
            again=rebuild(raw,Path(tmp)/'again')
            self.assertEqual(result,again)
            for name in ['accepted.parquet','needs_review.parquet']:
                self.assertEqual((out/name).read_bytes(),(Path(tmp)/'again'/name).read_bytes())
            with self.assertRaises(FileExistsError):rebuild(raw,out)

if __name__=='__main__':unittest.main()
