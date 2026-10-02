from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Quantities:
    """Single decomposition of an expected transfer quantity.

    Every operation (arrival, dispatch, cancellation and the state machine)
    reads this view instead of recomputing totals independently, so the
    receiving and transfer ledgers can never disagree about what happened.
    """

    expected: Decimal
    arrived: Decimal
    dispatched: Decimal
    cancelled: Decimal

    @property
    def live(self) -> Decimal:
        """Quantity that may still arrive (expected minus what was cancelled)."""
        return self.expected - self.cancelled

    @property
    def open_expected(self) -> Decimal:
        """Quantity not yet arrived and not yet cancelled."""
        return self.expected - self.arrived - self.cancelled

    @property
    def received_pending_dispatch(self) -> Decimal:
        """Quantity already on the dock, still awaiting shipment."""
        return self.arrived - self.dispatched


@dataclass(frozen=True)
class Transfer:
    transfer_id: str
    expected: Decimal
    arrived: Decimal = Decimal('0')
    dispatched: Decimal = Decimal('0')
    cancelled: Decimal = Decimal('0')
    exception: str | None = None


def quantities(t: Transfer) -> Quantities:
    return Quantities(t.expected, t.arrived, t.dispatched, t.cancelled)


def _qty(value: object) -> Decimal:
    q = Decimal(str(value))
    if q <= 0:
        raise ValueError('invalid quantity')
    return q


def arrival(t: Transfer, qty) -> Transfer:
    q = _qty(qty)
    split = quantities(t)
    if q > split.open_expected:
        raise ValueError('invalid arrival')
    return Transfer(
        t.transfer_id, t.expected, t.arrived + q, t.dispatched, t.cancelled, t.exception
    )


def dispatch(t: Transfer, qty) -> Transfer:
    q = _qty(qty)
    split = quantities(t)
    if q > split.received_pending_dispatch:
        raise ValueError('invalid dispatch')
    return Transfer(
        t.transfer_id, t.expected, t.arrived, t.dispatched + q, t.cancelled, t.exception
    )


# Explicit policies for cancelling part of the undelivered remainder while
# another part has already arrived. Callers must state what they want rather
# than having the state machine quietly reclassify received goods as cancelled.
KEEP_PARTIAL = 'keep_partial'  # keep the arrived part; status reflects the partial
MANUAL_EXCEPTION = 'manual_exception'  # park the transfer for human resolution


def cancel(t: Transfer, qty, on_partial: str) -> Transfer:
    """Cancel ``qty`` of the not-yet-arrived remainder.

    ``on_partial`` is required: with arrivals already on record the caller must
    either keep the partial completion (KEEP_PARTIAL) or turn the transfer into
    a manual exception (MANUAL_EXCEPTION). Repeating a cancellation with the
    same confirmed quantity is an idempotent no-op: confirmed (arrived,
    dispatched and already cancelled) quantities never move.
    """
    q = _qty(qty)
    split = quantities(t)
    if q > split.open_expected + split.cancelled:
        raise ValueError('invalid cancellation')

    # Idempotent retry of an already confirmed cancellation request.
    if q <= split.cancelled:
        if q != split.cancelled:
            raise ValueError('invalid cancellation')
        return t

    if split.arrived > 0 and on_partial not in (KEEP_PARTIAL, MANUAL_EXCEPTION):
        raise ValueError('on_partial must be KEEP_PARTIAL or MANUAL_EXCEPTION')

    cancelled = split.cancelled + q
    exception = t.exception
    if split.arrived > 0 and on_partial == MANUAL_EXCEPTION:
        exception = 'partial cancellation awaiting manual review'
    return Transfer(
        t.transfer_id, t.expected, t.arrived, t.dispatched, cancelled, exception
    )


def status(t: Transfer) -> str:
    if t.exception is not None:
        return 'exception'
    split = quantities(t)
    if split.open_expected > 0:
        # More goods may still arrive.
        if split.arrived > 0:
            return 'partial'
        return 'cancelled' if split.cancelled > 0 else 'planned'
    # Nothing left to arrive.
    if split.arrived == 0:
        # Everything outstanding was cancelled; no receiving fact exists.
        return 'cancelled'
    if split.received_pending_dispatch > 0:
        # Goods physically arrived but are not yet shipped. The cancellation
        # of the remainder must not re-label these goods as cancelled.
        return 'partial'
    # Everything that arrived has been dispatched; with KEEP_PARTIAL the
    # shortfall is recorded in cancelled while the transfer is done.
    return 'complete'
