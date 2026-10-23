"""Verify dedicated Conda provenance and GPU execution; emit JSON only."""
import importlib
import json
from pathlib import Path
import site
import subprocess
import sys

result = {'python': sys.version, 'executable': sys.executable, 'prefix': sys.prefix,
          'user_site_enabled': site.ENABLE_USER_SITE, 'packages': {}}
prefix = Path(sys.prefix).resolve()
assert not site.ENABLE_USER_SITE
for name in ['torch','torchvision','numpy','cv2','h5py','scipy','matplotlib','PIL','yaml','docx','pytest']:
    module = importlib.import_module(name)
    location = Path(module.__file__).resolve()
    assert location.is_relative_to(prefix), (name, str(location))
    result['packages'][name] = {'version': getattr(module,'__version__','unknown'), 'file': str(location)}
import torch
import numpy as np
assert torch.__version__.startswith('2.5.1')
assert torch.version.cuda == '11.8'
assert torch.cuda.is_available()
result['cuda'] = {'runtime': torch.version.cuda, 'device': torch.cuda.get_device_name(0),
                  'matrix_sum': float((torch.ones((16,16),device='cuda') @ torch.ones((16,16),device='cuda')).sum().cpu())}
result['numpy_bridge'] = torch.from_numpy(np.array([1,2],dtype=np.float32)).numpy().tolist()
for name in ['ffmpeg','ffprobe']:
    executable = prefix / 'Library/bin' / (name+'.exe')
    result[name] = subprocess.check_output([str(executable),'-version'], text=True, errors='replace').splitlines()[0]
result['status'] = 'passed'
print(json.dumps(result, ensure_ascii=False, indent=2))
