"""Log-Mel 特征提取（纯 numpy 实现，不依赖 torchaudio）。

输入：16 kHz 单声道波形，长度 1 秒（16000 点）
输出：40 x 98 的 log-Mel 特征图
    40  = Mel 滤波器个数（频率方向）
    98  = 帧数（时间方向）

这些参数和文档中的图一一对应，建议先看懂文档第 4 节再读代码。
"""

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SAMPLE_RATE = 16000      # 采样率 16 kHz
CLIP_SAMPLES = 16000     # 每条音频固定 1 秒
WIN_LENGTH = 400         # 25 ms 窗长（400 / 16000 = 0.025 s）
HOP_LENGTH = 160         # 10 ms 帧移（160 / 16000 = 0.01 s）
N_FFT = 512              # FFT 点数（补零到 512）
N_MELS = 40              # Mel 滤波器个数
N_FRAMES = 98            # (16000 - 400) / 160 + 1 = 98 帧


def hz_to_mel(freq):
    """频率 -> Mel 刻度。"""
    return 2595.0 * np.log10(1.0 + freq / 700.0)


def mel_to_hz(mel):
    """Mel 刻度 -> 频率。"""
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def make_mel_filterbank(sr=SAMPLE_RATE, n_fft=N_FFT, n_mels=N_MELS):
    """构造三角 Mel 滤波器组，形状为 (n_mels, n_fft // 2 + 1)。"""
    mel_points = np.linspace(hz_to_mel(0.0), hz_to_mel(sr / 2.0), n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mels + 1):
        left, center, right = bins[m - 1], bins[m], bins[m + 1]
        center = max(center, left + 1)
        right = max(right, center + 1)
        for k in range(left, center):
            fb[m - 1, k] = (k - left) / (center - left)
        for k in range(center, right):
            fb[m - 1, k] = (right - k) / (right - center)
    return fb


_MEL_FB = make_mel_filterbank()                    # 全局只算一次
_WINDOW = np.hanning(WIN_LENGTH).astype(np.float32)


def load_wav(path):
    """读取任意采样率的 wav，统一成 16 kHz 单声道 float32。"""
    wav, sr = sf.read(path, dtype="float32", always_2d=False)
    if wav.ndim > 1:                               # 立体声 -> 单声道
        wav = wav.mean(axis=1)
    if sr != SAMPLE_RATE:                          # 重采样到 16 kHz
        wav = resample_poly(wav, SAMPLE_RATE, sr).astype(np.float32)
    return wav


def wav_to_logmel(wav):
    """16 kHz 波形 -> (40, 98) log-Mel 特征。"""
    # 1) 统一长度：不足 1 秒补零，超过 1 秒截断
    if len(wav) < CLIP_SAMPLES:
        wav = np.pad(wav, (0, CLIP_SAMPLES - len(wav)))
    else:
        wav = wav[:CLIP_SAMPLES]

    # 2) 分帧 + 加 Hann 窗（np.hanning；指导文档文字写 Hamming，代码实际为 Hann）
    frames = np.lib.stride_tricks.sliding_window_view(wav, WIN_LENGTH)[::HOP_LENGTH]
    frames = frames * _WINDOW

    # 3) 短时傅里叶变换： (98, 400) -> (98, 257)
    spectrum = np.fft.rfft(frames, n=N_FFT)
    power = (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float32)

    # 4) Mel 滤波： (98, 257) x (257, 40) -> (98, 40)
    mel = power @ _MEL_FB.T

    # 5) 取对数，得到 (98, 40)，转置成网络喜欢的 (40, 98)
    logmel = np.log(mel + 1e-6)
    return logmel.T.astype(np.float32)


def load_and_featurize(path):
    """读音频 + 提取特征，给 DataLoader / 多进程调用。"""
    return wav_to_logmel(load_wav(path))
