import unittest
from decimal import Decimal
from coldledger.transfer.crossdock import Transfer,arrival,dispatch,cancel,cancel_remaining,status,open_quantity,on_hand
D=Decimal
class CrossdockTests(unittest.TestCase):
    def test_cancel_remainder_keeps_arrived_facts(self):
        t=cancel_remaining(dispatch(arrival(Transfer('T',D('10')),6),6))
        self.assertEqual((t.arrived,t.dispatched,t.cancelled),(D('6'),D('6'),D('4')))
        self.assertEqual(status(t),'partial_complete')
        self.assertEqual(status(t,on_partial='exception'),'exception')
    def test_partial_cancel_of_remainder_stays_partial(self):
        t=cancel(arrival(Transfer('T',D('10')),6),2)
        self.assertEqual(status(t),'partial')
        self.assertEqual(open_quantity(t),D('2'))
    def test_repeated_cancel_cannot_change_confirmed(self):
        t=cancel_remaining(arrival(Transfer('T',D('10')),6))
        again=cancel_remaining(t)
        self.assertEqual(again,t)
        self.assertEqual((again.arrived,again.dispatched),(D('6'),D('0')))
        with self.assertRaises(ValueError): cancel(again,1)
    def test_full_and_empty_outcomes(self):
        self.assertEqual(status(Transfer('T',D('4'))),'planned')
        t=arrival(Transfer('T',D('4')),4)
        self.assertEqual(status(t),'complete')
        self.assertEqual(on_hand(dispatch(t,4)),D('0'))
        self.assertEqual(status(cancel_remaining(Transfer('T',D('3')))),'cancelled')
    def test_guards(self):
        t=Transfer('T',D('2'))
        with self.assertRaises(ValueError): arrival(t,3)
        with self.assertRaises(ValueError): dispatch(t,1)
        with self.assertRaises(ValueError): cancel(t,0)
        with self.assertRaises(ValueError): status(t,on_partial='bogus')
if __name__=='__main__':unittest.main()
