import unittest
from vision.experiments.image import retrieval_metrics, rank_candidates, split_manifest

class ImageTests(unittest.TestCase):
    def test_hand_calculated_metrics(self):
        result=retrieval_metrics([True,False,True,False,False,True])
        self.assertAlmostEqual(result['p_at_5'],.4)
        self.assertAlmostEqual(result['ap'],(1+2/3+3/6)/3)

    def test_exclusion_and_tie_break(self):
        self.assertEqual(rank_candidates('query',['b','query','a','c'],[.8,1,.8,.2]),[2,0,3])

    def test_complete_disjoint_split(self):
        rows=split_manifest([f'obj{o}__{a}.png' for o in range(1,101) for a in range(0,360,5)])
        queries={r['id'] for r in rows if r['query']}
        full={r['id'] for r in rows if not r['query']}
        sparse={r['id'] for r in rows if r['sparse']}
        self.assertEqual((len(queries),len(full),len(sparse)),(400,6800,800))
        self.assertFalse(queries & full)
        self.assertTrue(sparse <= full)

if __name__=='__main__': unittest.main()
