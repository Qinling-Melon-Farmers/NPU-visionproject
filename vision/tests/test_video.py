"""Small semantic tests; no fake model scores are used as experiment results."""
import unittest
from vision.experiments.video import relevant, evaluate


class VideoSemantics(unittest.TestCase):
    def test_directional_temporal_relevance(self):
        query={'source_id':'a','start':10.,'end':30.}
        self.assertTrue(relevant(query,{'source_id':'a','start':14.,'end':34.}))
        self.assertFalse(relevant(query,{'source_id':'a','start':14.01,'end':34.01}))
        self.assertFalse(relevant(query,{'source_id':'b','start':10.,'end':30.}))

    def test_average_precision_and_hit(self):
        query={'id':'q','source_id':'a','start':0.,'end':20.}
        candidates=[{'id':'negative','source_id':'b','start':0.,'end':20.},
                    {'id':'positive','source_id':'a','start':0.,'end':20.}]
        result=evaluate({'q':{'negative':.8,'positive':.5}},[query],candidates)[0]
        self.assertEqual(result['hit_at_3'],1)
        self.assertEqual(result['ap'],.5)


if __name__=='__main__':
    unittest.main()
