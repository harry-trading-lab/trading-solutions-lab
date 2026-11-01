"""Replay cached V3 score events; retain exceptions and account for every input.

This standalone example does not import the private collector or model code.
It preserves source order. Score decreases are retained for review, never
silently repaired or accepted as validated basketball history.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import pandas as pd

COLUMNS = ['game_id', 'source_row', 'event_id', 'quarter',
           'time_remaining_seconds', 'home_score', 'away_score', 'score_decrease']


def integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f'{field}: boolean is not an integer')
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{field}: invalid integer') from None
    if not math.isfinite(number) or not number.is_integer() or number < 0:
        raise ValueError(f'{field}: invalid nonnegative integer')
    return int(number)


def blank(value):
    return value is None or bool(pd.isna(value)) or (isinstance(value, str) and not value.strip())


def parse_game(frame, game_id):
    required = {'gameId', 'actionNumber', 'period', 'clock', 'scoreHome', 'scoreAway'}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError('Empty game or missing V3 columns')
    if frame.gameId.isna().any() or set(frame.gameId.astype(str)) != {game_id}:
        raise ValueError('Raw game ID does not match the input filename')
    previous = (0, 0)
    states = [{'game_id': game_id, 'source_row': -1, 'event_id': -1,
               'quarter': 1, 'time_remaining_seconds': 2880.0,
               'home_score': 0, 'away_score': 0, 'score_decrease': False}]
    observed = 0
    for pos, row in enumerate(frame.to_dict('records')):
        h, a = row['scoreHome'], row['scoreAway']
        if blank(h) and blank(a):
            continue  # non-scoring rows, including an empty trailing row
        if blank(h) != blank(a):
            raise ValueError(f'row {pos}: incomplete score pair')
        score = (integer(h, 'scoreHome'), integer(a, 'scoreAway'))
        period = integer(row['period'], 'period')
        if period < 1:
            raise ValueError(f'row {pos}: invalid period')
        clock = re.fullmatch(r'PT(\d{1,2})M(\d{2}(?:\.\d+)?)S', str(row['clock']))
        if not clock:
            raise ValueError(f'row {pos}: invalid clock')
        minutes, seconds = int(clock[1]), float(clock[2])
        remaining = minutes * 60 + seconds
        if seconds >= 60 or remaining > (720 if period <= 4 else 300):
            raise ValueError(f'row {pos}: out-of-range clock')
        event_id = integer(row['actionNumber'], 'actionNumber')
        observed += 1
        if score == previous:
            continue
        states.append({'game_id': game_id, 'source_row': pos, 'event_id': event_id,
                       'quarter': period,
                       'time_remaining_seconds': (4-period)*720+remaining if period <= 4 else remaining,
                       'home_score': score[0], 'away_score': score[1],
                       'score_decrease': score[0] < previous[0] or score[1] < previous[1]})
        previous = score
    if not observed:
        raise ValueError('No populated score pairs')
    return states


def rebuild(raw_dir, output_dir):
    raw_dir, output_dir = Path(raw_dir), Path(output_dir)
    files = sorted(raw_dir.glob('*.parquet'))
    if not files:
        raise ValueError('No raw Parquet files')
    # A new directory prevents accidental replacement of an existing dataset.
    output_dir.mkdir(parents=True, exist_ok=False)
    accepted, review, manifest = [], [], []
    for path in files:
        item = {'game_id': path.stem, 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            rows = parse_game(pd.read_parquet(path), path.stem)
            decreases = sum(row['score_decrease'] for row in rows)
            item.update(status='needs_review' if decreases else 'accepted',
                        output_rows=len(rows), score_decreases=decreases)
            (review if decreases else accepted).extend(rows)
        except Exception as error:
            item.update(status='rejected', error_type=type(error).__name__, error=str(error))
        manifest.append(item)
    for name, rows in [('accepted', accepted), ('needs_review', review)]:
        pd.DataFrame(rows, columns=COLUMNS).to_parquet(output_dir / f'{name}.parquet', index=False)
    counts = {status: sum(x['status'] == status for x in manifest)
              for status in ['accepted', 'needs_review', 'rejected']}
    result = {'input_games': len(files), 'status_counts': counts,
              'accepted_rows': len(accepted), 'review_rows': len(review),
              'scope': 'Cached V3 score transitions, with source order preserved. Accepted means these checks passed, not verified game truth.',
              'games': manifest}
    (output_dir/'manifest.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    report = rebuild(args.raw_dir, args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != 'games'}, indent=2))
    raise SystemExit(2 if report['status_counts']['rejected'] or report['status_counts']['needs_review'] else 0)
