"""
BMAR Audio Conversion Module
Handles audio format conversion, downsampling, and encoding operations.
"""

import numpy as np
from pydub import AudioSegment
from math import gcd
try:
    # High-quality path if SciPy is present; otherwise we’ll fall back to linear interp
    from scipy.signal import resample_poly
except ImportError:
    resample_poly = None

__all__ = ["ensure_pcm16", "downsample_audio", "pcm_to_mp3_write"]

def ensure_pcm16(data: np.ndarray) -> np.ndarray:
    """
    Convert input array to contiguous int16 without normalization/AGC.
    - float -> clamp [-1,1] then scale to int16
    - int16 -> returned as-is
    - int32 -> downscale assuming 24-bit packed in 32-bit
    - other ints -> clip to int16 range
    """
    if data is None:
        raise ValueError("ensure_pcm16: data is None")
    arr = np.asarray(data)

    if arr.dtype == np.int16:
        return np.ascontiguousarray(arr)

    if np.issubdtype(arr.dtype, np.floating):
        f = arr.astype(np.float32, copy=False)
        f = np.nan_to_num(f, nan=0.0, posinf=0.0, neginf=0.0)
        f = np.clip(f, -1.0, 1.0)
        return np.ascontiguousarray((f * 32767.0).astype(np.int16))

    if arr.dtype == np.int32:
        scaled = np.clip(arr / 65536.0, -32768, 32767)
        return np.ascontiguousarray(scaled.astype(np.int16))

    info16 = np.iinfo(np.int16)
    clipped = np.clip(arr, info16.min, info16.max)
    # Return contiguous int16
    return np.ascontiguousarray(clipped.astype(np.int16))

def downsample_audio(x, in_sr: int, out_sr: int):
    """
    Resample from in_sr to out_sr without changing gain.
    Accepts mono or [N, C] arrays; supports int/float dtypes.
    Returns same dtype as input (no normalization).
    """
    a = np.asarray(x)
    if in_sr == out_sr:
        return a
    if in_sr <= 0 or out_sr <= 0:
        raise ValueError("downsample_audio: sample rates must be positive")

    orig_dtype = a.dtype

    # Convert to float32 for processing; remember integer scale to restore later
    if np.issubdtype(orig_dtype, np.integer):
        info = np.iinfo(orig_dtype)
        scale = float(max(abs(info.min), info.max)) or 1.0
        af = (a.astype(np.float32) / scale)
        int_scale = scale
    else:
        af = a.astype(np.float32, copy=False)
        af = np.nan_to_num(af, nan=0.0, posinf=0.0, neginf=0.0)
        int_scale = None

    if resample_poly is not None:
        g = gcd(int(in_sr), int(out_sr))
        up = int(out_sr // g)
        down = int(in_sr // g)
        y = resample_poly(af, up, down, axis=0)
    else:
        n_in = af.shape[0]
        n_out = int(round(n_in * (out_sr / float(in_sr))))
        t_in = np.linspace(0.0, 1.0, n_in, endpoint=False, dtype=np.float64)
        t_out = np.linspace(0.0, 1.0, n_out, endpoint=False, dtype=np.float64)
        if af.ndim == 1:
            y = np.interp(t_out, t_in, af).astype(np.float32)
        else:
            y = np.vstack([np.interp(t_out, t_in, af[:, ch]) for ch in range(af.shape[1])]).T.astype(np.float32)

    # Restore original dtype (preserve amplitude)
    if int_scale is not None:
        y = np.clip(y * int_scale, -int_scale, int_scale - 1).astype(orig_dtype)
    else:
        y = y.astype(orig_dtype, copy=False)

    return y

def pcm_to_mp3_write(np_array, full_path, config, sample_rate=None, bitrate_kbps=None, vbr_quality=None):
    """
    Export as MP3 using pydub/ffmpeg. Converts to PCM16 bytes first.
    """
    pcm16 = ensure_pcm16(np_array)
    channels = 1 if pcm16.ndim == 1 else pcm16.shape[1]
    # Use provided sample_rate if given; otherwise fall back to config
    sr = int(sample_rate) if sample_rate else (
        getattr(config, "SAVE_SAMPLE_RATE", None) or getattr(config, "PRIMARY_IN_SAMPLERATE", None) or 44100
    )

    export_kwargs = {"format": "mp3"}
    # Prefer explicit CBR if provided
    if bitrate_kbps is not None:
        export_kwargs["bitrate"] = f"{int(bitrate_kbps)}k"
    elif vbr_quality is not None:
        # Use ffmpeg VBR quality parameter
        export_kwargs["parameters"] = ["-q:a", str(int(vbr_quality))]
    else:
        # Fallback to config: treat 64-320 as kbps, 0-9 as VBR
        q = getattr(config, "AUDIO_MONITOR_QUALITY", 128)
        try:
            q = int(q)
        except (ValueError, TypeError):
            q = 128
        if 64 <= q <= 320:
            export_kwargs["bitrate"] = f"{q}k"
        elif 0 <= q <= 9:
            export_kwargs["parameters"] = ["-q:a", str(q)]
        else:
            export_kwargs["bitrate"] = "128k"

    seg = AudioSegment(
        data=pcm16.tobytes(),
        sample_width=2,
        frame_rate=int(sr),
        channels=int(channels),
    )
    seg.export(full_path, **export_kwargs)
