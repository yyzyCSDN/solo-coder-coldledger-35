import unittest
from decimal import Decimal
from coldledger.transfer import crossdock as xd
from coldledger.transfer.crossdock import (
    Transfer, arrival, dispatch, cancel, status, quantities,
    KEEP_PARTIAL, MANUAL_EXCEPTION,
)


class CrossdockTests(unittest.TestCase):
    def test_basic_lifecycle(self):
        t = Transfer('T1', Decimal('100'))
        t = arrival(t, 60)
        t = dispatch(t, 60)
        self.assertEqual(status(t), 'partial')  # 40 still open
        t = arrival(t, 40)
        t = dispatch(t, 40)
        self.assertEqual(status(t), 'complete')

    def test_cancel_remainder_after_partial_keeps_arrival_fact(self):
        # 100 expected, 60 arrived and dispatched; remaining 40 never arrives.
        t = Transfer('T2', Decimal('100'))
        t = arrival(t, 60)
        t = dispatch(t, 60)
        t2 = cancel(t, 40, KEEP_PARTIAL)
        # arrived/dispatched ledger facts are preserved
        self.assertEqual(t2.arrived, Decimal('60'))
        self.assertEqual(t2.dispatched, Decimal('60'))
        self.assertEqual(t2.cancelled, Decimal('40'))
        # decomposition closes: live = 60, nothing open
        q = quantities(t2)
        self.assertEqual(q.live, Decimal('60'))
        self.assertEqual(q.open_expected, Decimal('0'))
        self.assertEqual(status(t2), 'complete')

    def test_cancel_remainder_arrived_but_undispatched_is_partial_not_cancelled(self):
        t = Transfer('T3', Decimal('100'))
        t = arrival(t, 60)
        t = cancel(t, 40, KEEP_PARTIAL)
        # The state machine must not treat the 60 already on the dock as cancelled.
        self.assertEqual(status(t), 'partial')
        self.assertEqual(t.arrived, Decimal('60'))
        self.assertEqual(t.cancelled, Decimal('40'))
        # goods can still be shipped out
        t = dispatch(t, 60)
        self.assertEqual(status(t), 'complete')

    def test_partial_cancellation_does_not_report_cancelled(self):
        t = Transfer('T4', Decimal('100'))
        t = arrival(t, 30)
        t = cancel(t, 20, KEEP_PARTIAL)
        self.assertEqual(status(t), 'partial')  # old code said 'cancelled'
        self.assertEqual(quantities(t).open_expected, Decimal('50'))

    def test_full_cancel_before_arrival(self):
        t = Transfer('T5', Decimal('100'))
        t = cancel(t, 100, KEEP_PARTIAL)
        self.assertEqual(status(t), 'cancelled')

    def test_policy_required_when_arrived(self):
        t = arrival(Transfer('T6', Decimal('100')), 40)
        with self.assertRaises(ValueError):
            cancel(t, 60, None)
        with self.assertRaises(ValueError):
            cancel(t, 60, 'bogus')

    def test_manual_exception_policy(self):
        t = arrival(Transfer('T7', Decimal('100')), 40)
        t = cancel(t, 60, MANUAL_EXCEPTION)
        self.assertEqual(status(t), 'exception')
        self.assertIsNotNone(t.exception)
        # confirmed quantities unchanged
        self.assertEqual(t.arrived, Decimal('40'))
        self.assertEqual(t.cancelled, Decimal('60'))

    def test_repeated_cancel_is_idempotent_on_confirmed_quantities(self):
        t = arrival(Transfer('T8', Decimal('100')), 40)
        t = cancel(t, 60, KEEP_PARTIAL)
        again = cancel(t, 60, KEEP_PARTIAL)
        self.assertEqual(again, t)
        self.assertEqual(again.cancelled, Decimal('60'))
        self.assertEqual(again.arrived, Decimal('40'))
        # cannot cancel beyond the original remainder
        with self.assertRaises(ValueError):
            cancel(t, 61, KEEP_PARTIAL)
        # a smaller different amount is not a confirmed retry
        with self.assertRaises(ValueError):
            cancel(t, 30, KEEP_PARTIAL)

    def test_incremental_cancels(self):
        t = arrival(Transfer('T9', Decimal('100')), 10)
        t = cancel(t, 20, KEEP_PARTIAL)
        t = cancel(t, 30, KEEP_PARTIAL)
        self.assertEqual(t.cancelled, Decimal('50'))
        self.assertEqual(quantities(t).open_expected, Decimal('40'))
        self.assertEqual(status(t), 'partial')

    def test_overflow_guards(self):
        with self.assertRaises(ValueError):
            arrival(Transfer('T10', Decimal('10')), 0)
        with self.assertRaises(ValueError):
            arrival(Transfer('T10', Decimal('10')), 11)
        t = arrival(Transfer('T10', Decimal('10')), 5)
        with self.assertRaises(ValueError):
            dispatch(t, 6)
        with self.assertRaises(ValueError):
            cancel(t, 6, KEEP_PARTIAL)
        cancel(t, 5, KEEP_PARTIAL)  # exactly the open remainder: ok


if __name__ == '__main__':
    unittest.main()
