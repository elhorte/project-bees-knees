"""
BMAR Audio Devices Module
Handles audio device discovery, configuration, and management using sounddevice.
"""
from typing import Optional, Dict, Any, List, Tuple
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

def list_hostapi_indices_by_names(names: List[str]) -> List[int]:
    apis = sd.query_hostapis()
    out: List[int] = []
    for want in names or []:
        w = _norm(want)
        for i, a in enumerate(apis):
            an = _norm(a.get("name", ""))
            if an == w or (w and w in an):
                out.append(i)
                break
    return out

def _soft_order_by_hostapi(devices: List[dict], idxs: List[int], pref_api_indices: List[int]) -> List[int]:
    # Order indices by preferred hostapi order, but do not drop others
    def pref_key(i: int) -> int:
        api_idx = devices[i].get("hostapi", -1)
        try:
            return pref_api_indices.index(api_idx)
        except ValueError:
            return len(pref_api_indices)
    return sorted(idxs, key=pref_key)

def find_device_by_config(*_args,
                          strict: Optional[bool] = None,
                          desired_samplerate: Optional[int] = None,
                          desired_channels: Optional[int] = None,
                          **_kwargs) -> Optional[Dict[str, Any]]:
    """
    Locate an input device using configured criteria with a fixed sample rate.
    - Partial-match precedence: name tokens, else model tokens, else make tokens.
    - Host API is a soft preference (ordering), not a hard filter.
    - Only return devices that accept the requested samplerate/channels.
    - If strict and no matching device, raise RuntimeError.
    Returns dict: { index, name, hostapi, default_sample_rate, input_channels }.
    """
    spec = _cfg.device_search_criteria()
    devices = sd.query_devices()
    apis = sd.query_hostapis()

    # Desired params (no negotiation)
    cfg = _cfg.default_config()
    rate = int(desired_samplerate or getattr(cfg, "PRIMARY_IN_SAMPLERATE", 44100))
    chs = int(desired_channels or getattr(cfg, "SOUND_IN_CHS", 1))

    # Determine strictness if not explicitly provided
    if strict is None:
        strict = bool(spec and spec.get("strict"))

    # Candidate: input-capable
    input_idxs = [i for i, d in enumerate(devices) if (d.get("max_input_channels") or 0) > 0]

    # Token matching by precedence
    tokens_used: List[str] = []
    if spec["name_tokens"]:
        tokens_used = spec["name_tokens"]
    elif spec["model_tokens"]:
        tokens_used = spec["model_tokens"]
    elif spec["make_tokens"]:
        tokens_used = spec["make_tokens"]

    cand = input_idxs
    if tokens_used:
        cand = [i for i in cand if _match_all_tokens(devices[i].get("name", ""), tokens_used)]

    # Strict: if tokens provided and none matched, fail early
    if strict and tokens_used and not cand:
        parts = []
        if spec["name_tokens"]: parts.append(f"name~{spec['name_tokens']}")
        elif spec["model_tokens"]: parts.append(f"model~{spec['model_tokens']}")
        elif spec["make_tokens"]: parts.append(f"make~{spec['make_tokens']}")
        raise RuntimeError("Configured input device not found (" + ", ".join(parts) + ")")

    # Build soft hostapi preference order
    pref_indices: List[int] = []
    if spec["hostapi_name"]:
        pref_indices.extend(list_hostapi_indices_by_names([spec["hostapi_name"]]))
    # Add OS-level default prefs
    try:
        from .bmar_config import API_PREFERENCE_FOR_PLATFORM
        pref_indices.extend(list_hostapi_indices_by_names(API_PREFERENCE_FOR_PLATFORM()))
    except Exception:
        pass
    # User-specified index is strongest preference if valid
    user_idx = spec.get("hostapi_index")
    if isinstance(user_idx, int) and 0 <= user_idx < len(apis):
        pref_indices = [user_idx] + [i for i in pref_indices if i != user_idx]
    # Unique order
    seen = set()
    pref_indices = [x for x in pref_indices if not (x in seen or seen.add(x))]

    # Order candidates by preference
    cand = _soft_order_by_hostapi(devices, cand, pref_indices)

    # Filter by fixed sample rate support (no negotiation)
    def supports(i: int) -> bool:
        try:
            sd.check_input_settings(device=i, samplerate=rate, channels=chs)
            return True
        except Exception:
            return False

    cand = [i for i in cand if supports(i)]

    if not cand:
        msg = f"no input device supports samplerate={rate}Hz with channels={chs}"
        if strict:
            raise RuntimeError(msg)
        logging.error(msg)
        return None

    sel = cand[0]
    dev = devices[sel]
    api_name = apis[dev["hostapi"]]["name"]
    return {
        "index": sel,
        "name": dev.get("name"),
        "hostapi": api_name,
        "default_sample_rate": int(dev.get("default_samplerate") or 0),
        "input_channels": int(dev.get("max_input_channels") or 0),
    }

def get_audio_device_config(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """Back-compat wrapper."""
    return find_device_by_config(*args, **kwargs)

def device_default_samplerate(device_index: int) -> Optional[int]:
    try:
        v = sd.query_devices()[device_index].get("default_samplerate")
        return int(v) if v else None
    except Exception:
        return None

def probe_samplerates(device_index: int, channels: int, candidates: List[int]) -> Tuple[Optional[int], Dict[int, str]]:
    """
    Retained for compatibility, but fixed-rate policy advises against probing.
    Returns (None, errors) unless candidates contains exactly one rate supported.
    """
    results: Dict[int, str] = {}
    for rate in [r for r in candidates if r]:
        try:
            sd.check_input_settings(device=device_index, samplerate=int(rate), channels=int(channels))
            return int(rate), results
        except Exception as e:
            results[int(rate)] = str(e)
    return None, results

def negotiate_input_params(device_index: int,
                           desired_samplerate: Optional[int],
                           desired_channels: Optional[int]) -> Tuple[int, int]:
    """
    Pick a supported samplerate and channels for the device.
    Channels is clamped to device max input channels.
    Rate candidates: desired -> device default -> 192k, 96k, 48k, 44.1k.
    """
    try:
        dev = sd.query_devices()[device_index]
    except Exception as e:
        logging.error("Unable to query device %d: %s", device_index, e)
        # conservative fallback
        return 48000, 1

    max_in = int(dev.get("max_input_channels") or 0) or 1
    channels = min(int(desired_channels or max_in), max_in)

    default_sr = device_default_samplerate(device_index)
    candidates = []
    for r in [desired_samplerate, default_sr, 192000, 96000, 48000, 44100]:
        if r and r not in candidates:
            candidates.append(int(r))

    chosen, errors = probe_samplerates(device_index, channels, candidates)
    if chosen:
        return chosen, channels

    logging.error("No supported samplerate found for device %d (channels=%d). Tried: %s",
                  device_index, channels, ", ".join(map(str, candidates)))
    for rate, msg in errors.items():
        logging.debug("Samplerate %s failed: %s", rate, msg)
    # Final fallback
    return 48000, channels

def show_current_audio_devices(app=None) -> dict:
    """
    Print the current input device selection. Returns a dict or {}.
    Accepts `app` to read selected params; works if app is None.
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

    print("\nHost APIs:")
    for idx, api in enumerate(hostapis):
        name = api.get("name", "")
        def_in = api.get("default_input_device", -1)
        def_out = api.get("default_output_device", -1)
        print(f"  [{idx}] {name}  (default_in_dev={def_in}, default_out_dev={def_out})")

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
