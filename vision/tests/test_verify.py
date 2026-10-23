import json
from pathlib import Path
import tempfile
import unittest

from vision.common.verify import verify, metrics, relevant


class VerifyTests(unittest.TestCase):
    def test_missing_outputs_never_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            result=verify({},Path(temporary))
        self.assertEqual(result['status'],'incomplete')
        for name in ('image','video','summary'):
            self.assertTrue(any(p.startswith(name+':') for p in result['pending']))
            self.assertTrue(any(p.startswith(name+' fresh replay:') for p in result['pending']))
        self.assertEqual(result['checks'],[])

    def test_completed_labels_without_evidence_never_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in ('image','video','summary'):
                (root/name).mkdir()
                (root/name/'results.json').write_text(json.dumps({'status':'completed','results':[],'data':{'queries':[],'candidates':[]}}))
            result=verify({},root)
        self.assertEqual(result['status'],'incomplete')
        for name in ('image','video','summary'):
            self.assertTrue(any(p.startswith(name+':') for p in result['pending']))
            self.assertTrue(any(p.startswith(name+' fresh replay:') for p in result['pending']))
        self.assertEqual(result['checks'],[])

    def test_hand_calculated_ap_and_precision(self):
        precision,ap=metrics([True,False,True,False,False],5)
        self.assertAlmostEqual(precision,.4)
        self.assertAlmostEqual(ap,(1+2/3)/2)

    def test_relevance_requires_source_and_eighty_percent(self):
        query={'source_id':'a','start':10.,'end':30.}
        self.assertTrue(relevant(query,{'source_id':'a','start':14.,'end':34.}))
        self.assertFalse(relevant(query,{'source_id':'a','start':14.01,'end':34.}))
        self.assertFalse(relevant(query,{'source_id':'b','start':10.,'end':30.}))


if __name__=='__main__':unittest.main()
