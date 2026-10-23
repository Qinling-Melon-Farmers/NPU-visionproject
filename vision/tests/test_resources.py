"""Local-only resource safety tests; no HTTP or dependency installation."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from vision.common.resources import download, extract_archive, safe_member_path

class Response(io.BytesIO):
    def __init__(self,value,status=200,headers=None):
        super().__init__(value);self.status=status;self.headers=headers or {}

class FakeOpener:
    def __init__(self,responses):self.responses=list(responses);self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request)
        return self.responses.pop(0)

class ResourceTests(unittest.TestCase):
    def test_archive_traversal_and_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('../escape','C:/escape','a/../../escape','a\\..\\..\\escape','name:stream'):
                with self.assertRaises(ValueError):safe_member_path(root,name)
            archive=root/'unsafe.zip'
            with zipfile.ZipFile(archive,'w') as output:output.writestr('../escape',b'x')
            with self.assertRaises(ValueError):extract_archive(archive,root/'out')
            self.assertFalse((root.parent/'escape').exists())

    def test_non_destructive_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'test.zip';out=root/'out'
            with zipfile.ZipFile(archive,'w') as output:output.writestr('a.txt',b'original')
            extract_archive(archive,out);extract_archive(archive,out)
            (out/'a.txt').write_bytes(b'existing')
            with self.assertRaises(ValueError):extract_archive(archive,out)
            self.assertEqual((out/'a.txt').read_bytes(),b'existing')

    def test_ignored_range_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.bin';part=Path(str(path)+'.part')
            part.write_bytes(b'abc');Path(str(part)+'.json').write_text(json.dumps({'url':'https://public.example/model','validator':'"v1"'}))
            opener=FakeOpener([Response(b'abcdef',headers={'ETag':'"v1"','Content-Length':'6'})])
            digest=hashlib.sha256(b'abcdef').hexdigest()
            download('https://public.example/model',path,digest,opener=opener)
            self.assertEqual(part.read_bytes(),b'abc');self.assertEqual(path.read_bytes(),b'abcdef')
            self.assertEqual(opener.requests[0].get_header('Range'),'bytes=3-')

    def test_verified_resume_and_final_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.bin';part=Path(str(path)+'.part');part.write_bytes(b'abc')
            Path(str(part)+'.json').write_text(json.dumps({'url':'https://public.example/model','validator':'"v1"'}))
            opener=FakeOpener([Response(b'def',206,{'ETag':'"v1"','Content-Length':'3','Content-Range':'bytes 3-5/6'})])
            digest=hashlib.sha256(b'abcdef').hexdigest()
            download('https://public.example/model',path,digest,opener=opener)
            self.assertTrue(download('https://public.example/model',path,digest,opener=FakeOpener([]))['reused'])
            with self.assertRaises(ValueError):download('https://public.example/model',path,'0'*64,opener=FakeOpener([]))
            self.assertEqual(path.read_bytes(),b'abcdef')

if __name__=='__main__':unittest.main()
