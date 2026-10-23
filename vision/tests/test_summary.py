import itertools
import unittest
import numpy as np
from vision.experiments.summary import knapsack, f1_score, keyshot_summary

class SummaryTests(unittest.TestCase):
    def test_dp_matches_exhaustive(self):
        rng=np.random.default_rng(13)
        for _ in range(40):
            values=rng.integers(0,40,8); weights=rng.integers(1,12,8)
            for capacity in [0,1,10,25]:
                chosen=knapsack(values,weights,capacity)
                optimum=max(sum(values[i] for i in range(8) if bits[i]) for bits in itertools.product([0,1],repeat=8) if sum(weights[i] for i in range(8) if bits[i])<=capacity)
                self.assertEqual(sum(values[i] for i in chosen),optimum)
                self.assertLessEqual(sum(weights[i] for i in chosen),capacity)
    def test_f1_hand_calculation(self):
        self.assertAlmostEqual(f1_score([1,1,0,0],[1,0,1,0]),.5)
        self.assertEqual(f1_score([0,0],[0,0]),0)
        self.assertEqual(f1_score([1,0],[1,0]),1)
    def test_frame_budget_and_mapping(self):
        mask,chosen,frames,values=keyshot_summary(np.array([.2,.9]),np.array([0,5]),np.array([[0,1],[2,9]]),np.array([2,8]),10,.15)
        self.assertEqual(mask.sum(),0)
        np.testing.assert_allclose(frames[:5],.2)
        np.testing.assert_allclose(frames[5:],.9)
        self.assertEqual(chosen,[])
    def test_invalid_weights(self):
        with self.assertRaises(ValueError): knapsack([1],[0],4)

if __name__=='__main__': unittest.main()
