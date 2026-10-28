"""Offline order-plan builder. No network, SDK, credentials or order submission."""
from decimal import Decimal, InvalidOperation


def positive(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Expected a finite positive number") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("Expected a finite positive number")
    return number


def plan(*, side="BUY", quantity=10, entry="100.00", stop="98.00",
         repeats=4, first_id=1000, tick="0.01", max_shares=100):
    """repeats counts ADDITIONAL copies; all groups are concurrent, not a chain.

    IDs are local preview IDs. A real adapter must allocate valid IDs from TWS.
    Single synthetic equity contract, integer shares, limit entry + attached stop.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError("Side must be BUY or SELL")
    for name, value, minimum in [("quantity", quantity, 1), ("repeats", repeats, 0),
                                 ("first_id", first_id, 1), ("max_shares", max_shares, 1)]:
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if repeats > 99 or first_id + 2 * (repeats + 1) > 2147483647:
        raise ValueError("Preview size or ID range exceeded")
    entry, stop, tick = map(positive, (entry, stop, tick))
    if entry % tick or stop % tick:
        raise ValueError("Price does not conform to supplied tick size")
    if (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
        raise ValueError("Stop must be on the loss side of entry")
    groups = repeats + 1
    total = groups * quantity
    if total > max_shares:
        raise ValueError("Aggregate share cap exceeded")
    orders = []
    for group in range(groups):
        parent = first_id + group * 2
        common = {"group": group + 1, "symbol": "DEMO", "secType": "STK",
                  "totalQuantity": quantity, "transmit": False}
        orders.append(dict(common, orderId=parent, parentId=0, action=side,
                           orderType="LMT", lmtPrice=str(entry)))
        orders.append(dict(common, orderId=parent+1, parentId=parent,
                           action="SELL" if side == "BUY" else "BUY",
                           orderType="STP", auxPrice=str(stop)))
    return {"mode": "OFFLINE_PREVIEW", "additional_repeats": repeats,
            "groups": groups, "order_count": len(orders), "total_entry_shares": total,
            "entry_notional": str(entry * total),
            "stop_distance_exposure": str(abs(entry-stop) * total),
            "scope": "Concurrent original + copies; all transmit=False. Synthetic equity only. "
                     "Stop-distance exposure excludes gaps, slippage and fees; it is not a loss cap. "
                     "No TWS connection, native UI modification or sequential re-entry.",
            "orders": orders}
