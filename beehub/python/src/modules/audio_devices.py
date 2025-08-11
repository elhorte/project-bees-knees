"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using sounddevice.
"""

from typing import Optional, Dict, Any, List
import logging
import sounddevice as sd
from . import bmar_config as _cfg

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _match_all_tokens(hay: str, tokens: List[str]) -> bool:
    if not tokens:
        return True
    h = _norm(hay)
    return all(_norm(t) in h for t in tokens)

def _hostapi_indices_by_names(names: List[str]) -> List[int]:
    apis = sd.query_hostapis()
    out = []
    for want in names or []:
        for i, a in enumerate(apis):
            an = a.get("name", "")
            if _norm(an) == _norm(want) or _norm(want) in _norm(an):
                out.append(i); break
    return out

def find_device_by_config(*_args, **_kwargs) -> Optional[Dict[str, Any]]:
    """
    Locate an input device using configured criteria.
    Precedence: name tokens, else model tokens, else make tokens.
    If any selector is provided, selection is strict and raises on no match.
    Returns dict: { index, name, hostapi, default_sample_rate, input_channels }.
    """
    spec = _cfg.device_search_criteria()
    devices = sd.query_devices()
    apis = sd.query_hostapis()

    # Input-capable only
    cand = [i for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]

    # Host API constraints
    if spec["hostapi_index"] is not None:
        cand = [i for i in cand if devices[i]["hostapi"] == spec["hostapi_index"]]
    if spec["hostapi_name"]:
        idxs = _hostapi_indices_by_names([spec["hostapi_name"]])
        if idxs:
            cand = [i for i in cand if devices[i]["hostapi"] in idxs]

    # Apply matching by precedence (name -> model -> make)
    tokens_used: List[str] = []
    if spec["name_tokens"]:
        tokens_used = spec["name_tokens"]
    elif spec["model_tokens"]:
        tokens_used = spec["model_tokens"]
    elif spec["make_tokens"]:
        tokens_used = spec["make_tokens"]

    if tokens_used:
        cand = [i for i in cand if _match_all_tokens(devices[i].get("name", ""), tokens_used)]

    if spec["strict"] and not cand:
        parts = []
        if spec["name_tokens"]: parts.append(f"name~{spec['name_tokens']}")
        elif spec["model_tokens"]: parts.append(f"model~{spec['model_tokens']}")
        elif spec["make_tokens"]: parts.append(f"make~{spec['make_tokens']}")
        if spec["hostapi_name"]: parts.append(f"hostapi={spec['hostapi_name']}")
        if spec["hostapi_index"] is not None: parts.append(f"hostapi_idx={spec['hostapi_index']}")
        raise RuntimeError("Configured input device not found (" + ", ".join(parts) + ")")

    if not cand:
        logging.error("No input devices available.")
        return None

    sel = cand[0]
    dev = devices[sel]
    api_name = apis[dev["hostapi"]]["name"]
    return {
        "index": sel,
        "name": dev["name"],
        "hostapi": api_name,
        "default_sample_rate": int(dev.get("default_samplerate") or 0),
        "input_channels": int(dev.get("max_input_channels") or 0),
    }

def get_audio_device_config(*args, **kwargs) -> Optional[Dict[str, Any]]:
    return find_device_by_config(*args, **kwargs)

def show_current_audio_devices(app=None) -> dict:
    """
    Print the current input device selection. Returns a dict with details or {}.
    Accepts `app` to read device_index/samplerate/channels; works if app is None.
    """
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception as e:
        logging.error("Unable to query audio devices: %s", e)
        print("Unable to query audio devices:", e)
        return {}

    idx = getattr(app, "device_index", None) if app is not None else None
    if idx is None:
        print("No input device currently selected.")
        logging.info("No input device currently selected.")
        return {}

    try:
        idx = int(idx)
    except Exception:
        print(f"Current device index is invalid: {idx!r}")
        logging.error("Current device index is invalid: %r", idx)
        return {}

    if not (0 <= idx < len(devices)):
        print(f"Current device index out of range: {idx}")
        logging.error("Current device index out of range: %d", idx)
        return {}

    dev = devices[idx]
    api_name = hostapis[dev["hostapi"]]["name"]
    info = {
        "index": idx,
        "name": dev.get("name"),
        "hostapi": api_name,
        "default_sample_rate": dev.get("default_samplerate"),
        "input_channels": dev.get("max_input_channels"),
        "selected_samplerate": getattr(app, "samplerate", None) if app is not None else None,
        "selected_channels": getattr(app, "channels", None) if app is not None else None,
    }

    line = f"Current input device: [{info['index']}] {info['name']} via {info['hostapi']} (default_sr={info['default_sample_rate']}, max_in_ch={info['input_channels']})"
    print(line)
    logging.info(line)
    if info["selected_samplerate"] or info["selected_channels"]:
        print(f"Selected params -> samplerate={info['selected_samplerate']}, channels={info['selected_channels']}")
    return info

def list_audio_devices_detailed(*_args, **_kwargs) -> Dict[str, Any]:
    """
    Print all host APIs and devices (input and output). 
    Returns a dict with 'hostapis' and 'devices' (each device enriched with hostapi_name).
    """
    try:
        hostapis = sd.query_hostapis()
        devices = sd.query_devices()
    except Exception as e:
        logging.error("Unable to query audio devices: %s", e)
        print("Unable to query audio devices:", e)
        return {"hostapis": [], "devices": []}

    # Print host APIs
    print("\nHost APIs:")
    for idx, api in enumerate(hostapis):
        name = api.get("name", "")
        def_in = api.get("default_input_device", -1)
        def_out = api.get("default_output_device", -1)
        print(f"  [{idx}] {name}  (default_in_dev={def_in}, default_out_dev={def_out})")

    # Build enriched device list
    enriched = []
    for i, d in enumerate(devices):
        api_idx = d.get("hostapi", -1)
        api_name = hostapis[api_idx]["name"] if 0 <= api_idx < len(hostapis) else "Unknown"
        enriched.append({
            "index": i,
            "name": d.get("name"),
            "hostapi_index": api_idx,
            "hostapi_name": api_name,
            "max_input_channels": d.get("max_input_channels"),
            "max_output_channels": d.get("max_output_channels"),
            "default_samplerate": d.get("default_samplerate"),
            "default_low_input_latency": d.get("default_low_input_latency"),
            "default_low_output_latency": d.get("default_low_output_latency"),
            "default_high_input_latency": d.get("default_high_input_latency"),
            "default_high_output_latency": d.get("default_high_output_latency"),
        })

    # Print inputs, then outputs
    print("\nInput devices:")
    for info in enriched:
        if (info["max_input_channels"] or 0) > 0:
            print(f"  [{info['index']}] {info['name']}  via {info['hostapi_name']}  "
                  f"(in_ch={info['max_input_channels']}, default_sr={info['default_samplerate']})")

    print("\nOutput devices:")
    for info in enriched:
        if (info["max_output_channels"] or 0) > 0:
            print(f"  [{info['index']}] {info['name']}  via {info['hostapi_name']}  "
                  f"(out_ch={info['max_output_channels']}, default_sr={info['default_samplerate']})")

    logging.info("Listed %d host APIs and %d devices", len(hostapis), len(devices))
    return {"hostapis": hostapis, "devices": enriched}

# Some UIs call a simpler name; provide a back-compat alias.
def list_audio_devices(*args, **kwargs) -> Dict[str, Any]:
    return list_audio_devices_detailed(*args, **kwargs)
