"""O(log n) range queries/point revisions; immutable size, one symbol per tree.

Volume-weighted population variance over supplied bar prices. This is not
trade-level VWAP unless callers supply trades. Zero-volume bars carry no weight.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Moments:
    volume: float = 0.0
    mean: float = 0.0
    m2: float = 0.0

    @property
    def variance(self):
        return self.m2 / self.volume if self.volume else None

    def result(self):
        return {
            "volume": self.volume,
            "vwap": self.mean if self.volume else None,
            "variance": self.variance,
            "stddev": math.sqrt(max(0.0, self.variance)) if self.volume else None,
        }


def leaf(price, volume):
    if isinstance(price, bool) or isinstance(volume, bool):
        raise ValueError("price and volume must be finite numbers")
    try:
        price, volume = float(price), float(volume)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid price/volume") from exc
    # Bounded inputs also bound intermediate products in practical data sizes.
    if not math.isfinite(price) or not math.isfinite(volume):
        raise ValueError("non-finite price/volume")
    if abs(price) > 1e12 or not 0 <= volume <= 1e15:
        raise ValueError("price/volume outside supported domain")
    return Moments(volume, price, 0.0) if volume else Moments()


def merge(a, b):
    if not a.volume:
        return b
    if not b.volume:
        return a
    total = a.volume + b.volume
    delta = b.mean - a.mean
    return Moments(
        total,
        a.mean + delta * (b.volume / total),
        a.m2 + b.m2 + delta * delta * a.volume * (b.volume / total),
    )


class RangeVWAP:
    def __init__(self, bars):
        values = [leaf(p, v) for p, v in bars]
        self.length = len(values)
        self.size = 1
        while self.size < self.length:
            self.size *= 2
        self.nodes = [Moments() for _ in range(2 * self.size)]
        self.nodes[self.size : self.size + len(values)] = values
        for i in range(self.size - 1, 0, -1):
            self.nodes[i] = merge(self.nodes[2 * i], self.nodes[2 * i + 1])

    def query(self, start, stop):
        """Half-open [start, stop), indices into this symbol's ordered bars."""
        if type(start) is not int or type(stop) is not int:
            raise ValueError("indices must be integers")
        if not 0 <= start <= stop <= self.length:
            raise ValueError("invalid range")
        left, right = Moments(), Moments()
        start, stop = start + self.size, stop + self.size
        while start < stop:
            if start & 1:
                left = merge(left, self.nodes[start])
                start += 1
            if stop & 1:
                stop -= 1
                right = merge(self.nodes[stop], right)
            start //= 2
            stop //= 2
        return merge(left, right)

    def revise(self, index, price, volume):
        """Correct a bar and invalidate all affected ancestors, atomically on validation."""
        if type(index) is not int or not 0 <= index < self.length:
            raise ValueError("invalid bar index")
        value = leaf(price, volume)
        pos = self.size + index
        self.nodes[pos] = value
        pos //= 2
        while pos:
            self.nodes[pos] = merge(self.nodes[2 * pos], self.nodes[2 * pos + 1])
            pos //= 2
