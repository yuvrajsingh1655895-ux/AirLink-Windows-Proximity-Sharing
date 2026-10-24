import unittest
from proximity_policy import ProximityPolicy, State

class PolicyTests(unittest.TestCase):
    def setUp(self): self.p = ProximityPolicy()
    def test_unpaired_denied(self): self.assertEqual(self.p.evaluate(-45, True, False, [-45]*3).state, State.UNPAIRED)
    def test_disconnected_denied(self): self.assertEqual(self.p.evaluate(-45, False, True, [-45]*3).state, State.DISCONNECTED)
    def test_stale_denied(self): self.assertEqual(self.p.evaluate(-45, True, True, [-45]*3, fresh=False).state, State.STALE)
    def test_weak_signal_denied(self): self.assertFalse(self.p.evaluate(-75, True, True, [-75]*3).allowed)
    def test_stable_strong_signal_allowed(self): self.assertTrue(self.p.evaluate(-48, True, True, [-49,-48,-47]).allowed)
    def test_too_few_samples_denied(self): self.assertEqual(self.p.evaluate(-48, True, True, [-48]).state, State.UNSTABLE)

if __name__ == "__main__": unittest.main()
