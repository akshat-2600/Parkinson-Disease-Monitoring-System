"""
app/services/voice_service.py

Updated pipeline:
  1. Extract 22 voice biomarker features from audio
  2. Select the 15 features in selected_features.pkl  (ReliefF top-15)
  3. Scale with scaler_voice.pkl  (StandardScaler fit on selected features)
  4. Predict with pso_elm_parkinsons_model.pkl  (PSO-ELM; 92.31%)

The selected_features list from the training notebook:
  ['PPE', 'spread1', 'MDVP:Fo(Hz)', 'spread2', 'MDVP:Jitter(Abs)',
   'MDVP:APQ', 'MDVP:Flo(Hz)', 'MDVP:Fhi(Hz)', 'HNR', 'NHR',
   'MDVP:Jitter(%)', 'Shimmer:APQ5', 'MDVP:Shimmer(dB)',
   'Shimmer:APQ3', 'Shimmer:DDA']
"""
import os
import numpy as np
import logging
import warnings

logger = logging.getLogger(__name__)

# ── All 22 raw voice features (UCI Parkinson's dataset) ──────
VOICE_FEATURES = [
    "MDVP:Fo(Hz)", "MDVP:Fhi(Hz)", "MDVP:Flo(Hz)",
    "MDVP:Jitter(%)", "MDVP:Jitter(Abs)", "MDVP:RAP", "MDVP:PPQ", "Jitter:DDP",
    "MDVP:Shimmer", "MDVP:Shimmer(dB)", "Shimmer:APQ3", "Shimmer:APQ5",
    "MDVP:APQ", "Shimmer:DDA",
    "NHR", "HNR",
    "RPDE", "DFA", "spread1", "spread2", "D2", "PPE",
]

# Default selected features (ReliefF top-15) —
# overridden at runtime by the loaded selected_features.pkl
_DEFAULT_SELECTED_FEATURES = [
    "PPE", "spread1", "MDVP:Fo(Hz)", "spread2", "MDVP:Jitter(Abs)",
    "MDVP:APQ", "MDVP:Flo(Hz)", "MDVP:Fhi(Hz)", "HNR", "NHR",
    "MDVP:Jitter(%)", "Shimmer:APQ5", "MDVP:Shimmer(dB)",
    "Shimmer:APQ3", "Shimmer:DDA",
]


# ──────────────────────────────────────────────────────────────
# Audio feature extraction
# ──────────────────────────────────────────────────────────────

def extract_voice_features(audio_path: str) -> dict:
    """
    Extract Parkinson's voice biomarkers from an audio file.
    Returns a dict with all 22 keys from VOICE_FEATURES.
    """
    try:
        import parselmouth
        from parselmouth.praat import call
        import librosa

        sound   = parselmouth.Sound(audio_path)
        y, sr   = librosa.load(audio_path, sr=None, mono=True)

        # ── F0 ───────────────────────────────────────────────
        pitch    = sound.to_pitch()
        f0_vals  = pitch.selected_array["frequency"]
        f0_vals  = f0_vals[f0_vals > 0]

        fo  = float(np.mean(f0_vals))  if len(f0_vals) else 0.0
        fhi = float(np.max(f0_vals))   if len(f0_vals) else 0.0
        flo = float(np.min(f0_vals))   if len(f0_vals) else 0.0

        # ── Jitter ───────────────────────────────────────────
        pp          = call(sound, "To PointProcess (periodic, cc)", 75, 500)
        jitter_pct  = call(pp, "Get jitter (local)",          0, 0, 0.0001, 0.02, 1.3)
        jitter_abs  = call(pp, "Get jitter (local, absolute)", 0, 0, 0.0001, 0.02, 1.3)
        rap         = call(pp, "Get jitter (rap)",             0, 0, 0.0001, 0.02, 1.3)
        ppq         = call(pp, "Get jitter (ppq5)",            0, 0, 0.0001, 0.02, 1.3)
        ddp         = rap * 3

        # ── Shimmer ──────────────────────────────────────────
        try:
            shimmer    = call([sound, pp], "Get shimmer (local)",    0, 0, 0.0001, 0.02, 1.3, 1.6)
            shimmer_db = call([sound, pp], "Get shimmer (local, dB)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
            apq3       = call([sound, pp], "Get shimmer (apq3)",     0, 0, 0.0001, 0.02, 1.3, 1.6)
            apq5       = call([sound, pp], "Get shimmer (apq5)",     0, 0, 0.0001, 0.02, 1.3, 1.6)
            apq        = call([sound, pp], "Get shimmer (apq11)",    0, 0, 0.0001, 0.02, 1.3, 1.6)
            dda        = apq3 * 3
        except Exception as exc:
            logger.warning("Shimmer calc failed: %s", exc)
            shimmer = shimmer_db = apq3 = apq5 = apq = dda = 0.0

        # ── HNR / NHR ────────────────────────────────────────
        harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr         = call(harmonicity, "Get mean", 0, 0)
        nhr         = 1.0 / (10 ** (hnr / 10)) if hnr > 0 else 0.0

        # ── Nonlinear features ───────────────────────────────
        if len(f0_vals) > 1:
            f0_norm = f0_vals / (f0_vals.max() + 1e-9)
            hist, _ = np.histogram(f0_norm, bins=20, density=True)
            hist   += 1e-10
            rpde    = float(-np.sum(hist * np.log(hist)) / np.log(len(hist)))
        else:
            rpde = 0.5

        dfa = _compute_dfa(y)
        spread1, spread2, d2, ppe = _compute_nonlinear(f0_vals)

        return {
            "MDVP:Fo(Hz)":      fo,
            "MDVP:Fhi(Hz)":     fhi,
            "MDVP:Flo(Hz)":     flo,
            "MDVP:Jitter(%)":   jitter_pct,
            "MDVP:Jitter(Abs)": jitter_abs,
            "MDVP:RAP":         rap,
            "MDVP:PPQ":         ppq,
            "Jitter:DDP":       ddp,
            "MDVP:Shimmer":     shimmer,
            "MDVP:Shimmer(dB)": shimmer_db,
            "Shimmer:APQ3":     apq3,
            "Shimmer:APQ5":     apq5,
            "MDVP:APQ":         apq,
            "Shimmer:DDA":      dda,
            "NHR":              nhr,
            "HNR":              hnr,
            "RPDE":             rpde,
            "DFA":              dfa,
            "spread1":          spread1,
            "spread2":          spread2,
            "D2":               d2,
            "PPE":              ppe,
        }

    except Exception as exc:
        logger.error("Voice feature extraction failed: %s", exc)
        raise ValueError(f"Audio feature extraction failed: {exc}") from exc


def _compute_dfa(signal: np.ndarray, min_box: int = 4, max_box=None) -> float:
    n = len(signal)
    if n < 16:
        return 0.7
    if max_box is None:
        max_box = n // 4
    y_cum      = np.cumsum(signal - np.mean(signal))
    box_sizes  = np.unique(np.logspace(np.log10(min_box), np.log10(max_box), 20).astype(int))
    flucts     = []
    for box in box_sizes:
        if box < 2:
            continue
        n_boxes = n // box
        if n_boxes < 1:
            continue
        rms = []
        for i in range(n_boxes):
            seg  = y_cum[i * box:(i + 1) * box]
            x    = np.arange(len(seg))
            poly = np.polyfit(x, seg, 1)
            rms.append(np.sqrt(np.mean((seg - np.polyval(poly, x)) ** 2)))
        flucts.append(np.mean(rms))
    if len(flucts) < 2:
        return 0.7
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        slope, _ = np.polyfit(np.log(box_sizes[:len(flucts)]), np.log(flucts), 1)
    return float(np.clip(slope, 0.0, 2.0))


def _compute_nonlinear(f0_vals: np.ndarray):
    if len(f0_vals) < 5:
        return -5.0, 0.3, 2.3, 0.28
    log_f0  = np.log(f0_vals + 1e-9)
    spread1 = float(np.mean(log_f0) - np.log(np.mean(f0_vals) + 1e-9))
    spread2 = float(np.std(log_f0))
    d2      = float(np.clip(2.0 + np.random.normal(0, 0.1), 1.5, 3.5))
    diff    = np.abs(np.diff(f0_vals))
    if diff.sum() > 0:
        p   = diff / diff.sum()
        ppe = float(-np.sum(p * np.log(p + 1e-9)) / np.log(len(p) + 1))
    else:
        ppe = 0.0
    return spread1, spread2, d2, ppe


# ──────────────────────────────────────────────────────────────
# Main prediction pipeline
# ──────────────────────────────────────────────────────────────

def predict_from_audio(audio_path: str, model, scaler=None,
                       selector=None, selected_features=None) -> dict:
    """
    Full pipeline: audio → features → feature selection → scale → PSO-ELM predict.

    New pipeline (training notebook compatible):
      1. Extract all 22 VOICE_FEATURES
      2. Select the 15 features from selected_features (loaded pkl)
      3. Scale with scaler (fit on the 15 selected features)
      4. Predict with PSO-ELM model

    Args:
        audio_path:        path to audio file
        model:             PSO-ELM model object (has predict_proba)
        scaler:            StandardScaler (fit on selected features)
        selector:          optional; not used in new pipeline
        selected_features: list[str] of 15 feature names to select

    Returns dict with: has_parkinson, probability, confidence, severity, label, features
    """
    # ── Step 1: Extract all 22 features ──────────────────────
    features = extract_voice_features(audio_path)

    # ── Step 2: Select features ───────────────────────────────
    sel_feats = selected_features if selected_features is not None else _DEFAULT_SELECTED_FEATURES

    # If sel_feats is a list of strings, use it directly.
    # Handle edge case where it might be stored as a numpy array.
    if hasattr(sel_feats, "tolist"):
        sel_feats = sel_feats.tolist()

    try:
        x_selected = np.array([[features[f] for f in sel_feats]], dtype=np.float64)
    except KeyError as exc:
        logger.warning("Selected feature %s not found in extracted features; using all 22", exc)
        x_selected = np.array([[features[f] for f in VOICE_FEATURES]], dtype=np.float64)
        sel_feats  = VOICE_FEATURES

    # ── Step 3: Scale ─────────────────────────────────────────
    if scaler is not None:
        try:
            # Align columns if scaler has feature_names_in_
            if hasattr(scaler, "feature_names_in_"):
                import pandas as pd
                df = pd.DataFrame(x_selected, columns=sel_feats)
                df = df.reindex(columns=list(scaler.feature_names_in_), fill_value=0.0)
                x_selected = scaler.transform(df.values)
            else:
                x_selected = scaler.transform(x_selected)
        except Exception as exc:
            logger.warning("Voice scaler.transform failed: %s — proceeding unscaled", exc)

    # ── Step 4: Align to model expected input ─────────────────
    n_in = getattr(model, "n_features_in_", None)
    if n_in is not None and x_selected.shape[1] != n_in:
        if x_selected.shape[1] > n_in:
            logger.warning("Truncating voice vector %d → %d", x_selected.shape[1], n_in)
            x_selected = x_selected[:, :n_in]
        else:
            logger.warning("Padding voice vector %d → %d", x_selected.shape[1], n_in)
            pad        = np.zeros((1, n_in), dtype=x_selected.dtype)
            pad[:, :x_selected.shape[1]] = x_selected
            x_selected = pad

    # ── Step 5: PSO-ELM predict ───────────────────────────────
    proba     = model.predict_proba(x_selected)[0]
    label_idx = int(np.argmax(proba))
    prob_pd   = float(proba[1]) if len(proba) > 1 else float(proba[label_idx])
    has_pd    = prob_pd >= 0.5
    conf      = float(max(proba))

    return {
        "has_parkinson": has_pd,
        "probability":   prob_pd,
        "confidence":    conf,
        "severity":      round(prob_pd * 100, 2),
        "label":         "Parkinson's Detected" if has_pd else "No Parkinson's Detected",
        "features":      features,   # all 22 — used by explainability service
    }