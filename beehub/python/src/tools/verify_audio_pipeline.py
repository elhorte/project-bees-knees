import logging
import numpy as np
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.audio_conversion import ensure_pcm16
import soundfile as sf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def report(tag, x):
    x = np.asarray(x)
    logging.info(
        "%s: dtype=%s shape=%s min=%.6f max=%.6f mean=%.6f rms=%.6f absmax=%.6f",
        tag, x.dtype, x.shape, float(x.min()), float(x.max()),
        float(x.mean()), float(np.sqrt(np.mean(np.square(x.astype(np.float64))))),
        float(np.max(np.abs(x)))
    )

# Fake snapshot examples: replace with your real circular-buffer snapshot
def run_check(snapshot, sr):
    report("snapshot(raw)", snapshot)
    pcm16 = ensure_pcm16(snapshot)
    report("snapshot(pcm16)", pcm16)
    sf.write("verify.flac", pcm16, sr, subtype="PCM_16", format="FLAC")
    logging.info("Wrote verify.flac")

if __name__ == "__main__":
    # Replace with a real buffer slice while BMAR is running:
    sr = 192000
    silence = (np.random.randn(192000, 2) * 1e-5).astype(np.float32)
    run_check(silence, sr)