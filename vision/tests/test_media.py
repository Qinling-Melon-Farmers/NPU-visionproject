"""Real local FFmpeg decode/stride test; no network and no OpenCV Video I/O."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from vision.common.media import _tool,iter_frames,probe_video,read_frame,sample_frames

class MediaTests(unittest.TestCase):
    def test_exact_frames_sampling_and_rgb(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sequence.mkv'
            # Lossless constant RGB frames make frame identity and RGB order unambiguous.
            frames=np.zeros((12,32,48,3),dtype=np.uint8)
            for index in range(12):frames[index,:,:]=[index*15,20,200-index*10]
            result=subprocess.run([_tool('ffmpeg'),'-v','error','-f','rawvideo','-pix_fmt','rgb24',
                '-s','48x32','-r','6','-i','pipe:0','-c:v','ffv1','-pix_fmt','bgr0',str(path)],input=frames.tobytes(),stderr=subprocess.PIPE)
            self.assertEqual(result.returncode,0,result.stderr)
            info=probe_video(path)
            self.assertEqual((info['width'],info['height'],info['frame_count'],info['fps']),(48,32,12,6))
            decoded=np.array(list(iter_frames(path)))
            np.testing.assert_array_equal(decoded,frames)
            np.testing.assert_array_equal(read_frame(path,1),frames[6])
            sampled=sample_frames(path,fps=2,cc_size=None,rs_size=None)
            np.testing.assert_array_equal(sampled,frames[[0,3,6,9]])
            # Author uses Python round: 6/2.4 == 2.5 rounds to the even stride 2.
            np.testing.assert_array_equal(sample_frames(path,fps=2.4,cc_size=None,rs_size=None),frames[::2])
            cropped=sample_frames(path,fps=2)
            self.assertEqual(cropped.shape,(4,224,224,3))
            for i,index in enumerate([0,3,6,9]):np.testing.assert_array_equal(cropped[i,100,100],frames[index,0,0])

if __name__=='__main__':unittest.main()
