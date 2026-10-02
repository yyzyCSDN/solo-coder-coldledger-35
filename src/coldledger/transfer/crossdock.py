from dataclasses import dataclass
from decimal import Decimal

# Single quantity decomposition shared by arrival, dispatch, cancel and status:
#   expected = arrived + cancelled + open_quantity   (inbound view)
#   arrived  = dispatched + on_hand                  (outbound view)
# arrived/dispatched are confirmed ledger facts: cancellation may only consume
# open_quantity and must never reclassify confirmed quantities as cancelled.

@dataclass(frozen=True)
class Transfer: transfer_id:str;expected:Decimal;arrived:Decimal=Decimal('0');dispatched:Decimal=Decimal('0');cancelled:Decimal=Decimal('0')

def validate(t):
    if min(t.arrived,t.dispatched,t.cancelled)<0:raise ValueError('negative quantity')
    if t.dispatched>t.arrived:raise ValueError('dispatched exceeds arrived')
    if t.arrived+t.cancelled>t.expected:raise ValueError('arrived plus cancelled exceeds expected')

def open_quantity(t):return t.expected-t.arrived-t.cancelled
def on_hand(t):return t.arrived-t.dispatched

def arrival(t,qty):
    validate(t);q=Decimal(str(qty))
    if q<=0 or q>open_quantity(t):raise ValueError('invalid arrival')
    return Transfer(t.transfer_id,t.expected,t.arrived+q,t.dispatched,t.cancelled)

def dispatch(t,qty):
    validate(t);q=Decimal(str(qty))
    if q<=0 or q>on_hand(t):raise ValueError('invalid dispatch')
    return Transfer(t.transfer_id,t.expected,t.arrived,t.dispatched+q,t.cancelled)

def cancel(t,qty):
    validate(t);q=Decimal(str(qty))
    if q<=0 or q>open_quantity(t):raise ValueError('invalid cancellation')
    return Transfer(t.transfer_id,t.expected,t.arrived,t.dispatched,t.cancelled+q)

def cancel_remaining(t):
    # Idempotent: repeating the cancellation of the undelivered remainder is a
    # no-op, so confirmed quantities (arrived, dispatched) can never change.
    rest=open_quantity(t)
    if rest<=0:return t
    return cancel(t,rest)

PARTIAL_POLICIES=('partial_complete','exception')

def status(t,on_partial='partial_complete'):
    validate(t)
    if on_partial not in PARTIAL_POLICIES:raise ValueError('unknown partial policy')
    if open_quantity(t)>0:return 'partial' if t.arrived>0 else 'planned'
    if t.cancelled==0:return 'complete'
    if t.arrived==0:return 'cancelled'
    # Remainder cancelled but arrivals confirmed: the caller explicitly keeps
    # the partial completion or escalates the transfer to a manual exception.
    return on_partial
