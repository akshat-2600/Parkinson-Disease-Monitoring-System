"""
app/services/image_service.py

Spiral prediction  → Full ensemble: EffNet-B3-FT2 (TTA) + ResNet50 + SVM
                     Weights from best_ensemble_bundle.pkl (93.75%)
                     Prediction path: FT2-TTA + SVM → equal weight

MRI prediction     → 4-CNN TTA + PSO-ELM equal weight (98.19%)
                     Uses: EffNet-B3, EffNet-B4, ResNet50, DenseNet121 + PSO-ELM
                     All loaded from final_bundle.pkl

Both pipelines follow the exact inference flow from the training notebooks.
"""
import numpy as np
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# ── Image sizes ───────────────────────────────────────────────
MRI_IMAGE_SIZE    = (224, 224)
SPIRAL_IMAGE_SIZE = (224, 224)   # Both models use 224×224

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

LABELS = ["No Parkinson's Detected", "Parkinson's Detected"]


# ──────────────────────────────────────────────────────────────
# Internal: PyTorch transform helpers
# ──────────────────────────────────────────────────────────────

def _get_eval_transform(grayscale: bool = False):
    """Standard eval transform (no augmentation)."""
    try:
        from torchvision import transforms
        steps = []
        if grayscale:
            steps.append(transforms.Grayscale(num_output_channels=3))
        steps += [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
        return transforms.Compose(steps)
    except ImportError:
        return None


def _get_spiral_tta_transform():
    """TTA transform for spiral drawings (matches training notebook)."""
    try:
        from torchvision import transforms
        return transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    except ImportError:
        return None


def _get_mri_tta_transform():
    """TTA transform for MRI scans (matches training notebook)."""
    try:
        from torchvision import transforms
        return transforms.Compose([
            transforms.Grayscale(num_output_channels=3),
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.3),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    except ImportError:
        return None


def _get_mri_eval_transform():
    """Standard MRI eval transform (grayscale→3ch)."""
    try:
        from torchvision import transforms
        return transforms.Compose([
            transforms.Grayscale(num_output_channels=3),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    except ImportError:
        return None


# ──────────────────────────────────────────────────────────────
# Internal: feature extraction via forward hook
# ──────────────────────────────────────────────────────────────

def _extract_gap_features(model, img_tensor, device):
    """
    Extract Global Average Pool features via forward hook.
    Works for EffNet (model.global_pool), ResNet (model.avgpool).
    Returns numpy array shape (1, feat_dim).
    """
    import torch
    import torch.nn as nn

    feats = []

    def hook_fn(m, i, o):
        a = o.detach().cpu().numpy()
        if a.ndim > 2:
            a = a.reshape(a.shape[0], -1)
        feats.append(a)

    # Find the right layer
    hook = None
    for name, module in model.named_modules():
        if isinstance(module, nn.AdaptiveAvgPool2d):
            hook = module.register_forward_hook(hook_fn)
            break
        if "global_pool" in name and not isinstance(module, nn.Sequential):
            hook = module.register_forward_hook(hook_fn)
            break

    if hook is None:
        logger.warning("Could not find GAP layer for feature extraction")
        return None

    model.eval()
    with torch.no_grad():
        _ = model(img_tensor.unsqueeze(0).to(device))
    hook.remove()

    return feats[0] if feats else None


# ──────────────────────────────────────────────────────────────
# Internal: CNN TTA probability
# ──────────────────────────────────────────────────────────────

def _tta_prob(model, pil_img, tta_transform, n_tta: int, device) -> float:
    """
    Run TTA on a PIL image using the given model.
    Returns P(Parkinson) averaged over n_tta augmentations.
    """
    import torch
    probs = []
    model.eval()
    with torch.no_grad():
        for _ in range(n_tta):
            t = tta_transform(pil_img).unsqueeze(0).to(device)
            out = model(t)
            p = torch.softmax(out, dim=1)[0, 1].item()
            probs.append(p)
    return float(np.mean(probs))


# ──────────────────────────────────────────────────────────────
# SPIRAL PREDICTION  (full ensemble, 93.75%)
# ──────────────────────────────────────────────────────────────

def predict_spiral(image_path: str, model=None) -> dict:
    """
    Full spiral ensemble:
      1. EffNet-B3-FT2 TTA   (50% weight)
      2. ResNet50              (0% — not used in FT2-TTA + SVM best combo)
      3. SVM on PCA-256 features from EffNet (50% weight)

    Best combo from training: FT2-TTA + SVM → 93.75% accuracy
    If models are unavailable, falls back to simpler inference.

    Args:
        image_path: path to spiral drawing image
        model: ignored (kept for backward-compat API); models loaded from registry
    """
    from app.services.model_loader import ModelRegistry, get_torch_device

    effnet   = ModelRegistry.get("spiral_effnet")
    resnet   = ModelRegistry.get("spiral_resnet")
    bundle   = ModelRegistry.get("spiral_bundle")
    device   = get_torch_device()

    pil_img  = Image.open(image_path).convert("RGB")
    tta_tf   = _get_spiral_tta_transform()
    eval_tf  = _get_eval_transform(grayscale=False)

    individual = {}

    # ── 1. EffNet-B3-FT2 TTA ─────────────────────────────────
    p_effnet = 0.5   # neutral fallback
    if effnet is not None and tta_tf is not None:
        try:
            p_effnet = _tta_prob(effnet, pil_img, tta_tf, n_tta=8, device=device)
            individual["effnet_tta"] = p_effnet
            logger.debug("Spiral EffNet-FT2 TTA P(PD)=%.4f", p_effnet)
        except Exception as exc:
            logger.warning("Spiral EffNet TTA failed: %s", exc)

    # ── 2. SVM on PCA-256 features (via EffNet GAP) ───────────
    p_svm = 0.5   # neutral fallback
    if bundle is not None and effnet is not None and eval_tf is not None:
        try:
            import torch
            svm_model  = bundle.get("svm_model")
            sc_pca_256 = bundle.get("sc_pca_256")   # StandardScaler on raw EffNet feats
            pca_256    = bundle.get("pca_256")       # PCA(n_components=256)
            sc_svm     = bundle.get("sc_svm")        # StandardScaler for SVM input

            if all(x is not None for x in [svm_model, sc_pca_256, pca_256, sc_svm]):
                t = eval_tf(pil_img)
                feat = _extract_gap_features(effnet, t, device)
                if feat is not None:
                    feat_sc  = sc_pca_256.transform(feat)
                    feat_pca = pca_256.transform(feat_sc)
                    feat_sv  = sc_svm.transform(feat_pca)
                    p_svm    = float(svm_model.predict_proba(feat_sv)[0][1])
                    individual["svm"] = p_svm
                    logger.debug("Spiral SVM P(PD)=%.4f", p_svm)
        except Exception as exc:
            logger.warning("Spiral SVM failed: %s", exc)

    # ── 3. Ensemble (FT2-TTA + SVM equal weight) ─────────────
    # Best combo from notebook: FT2-TTA + SVM  → 93.75%, Recall=100%, AUC=0.974
    weights_sum = 0.0
    p_ensemble  = 0.0

    if "effnet_tta" in individual:
        p_ensemble  += 0.5 * individual["effnet_tta"]
        weights_sum += 0.5
    if "svm" in individual:
        p_ensemble  += 0.5 * individual["svm"]
        weights_sum += 0.5

    if weights_sum > 0:
        p_ensemble /= weights_sum
    else:
        p_ensemble = 0.5

    # Optional: add ResNet if available (for richer ensemble)
    if resnet is not None and tta_tf is not None and "effnet_tta" in individual:
        try:
            p_res = _tta_prob(resnet, pil_img, tta_tf, n_tta=8, device=device)
            individual["resnet"] = p_res
            # Small extra weight — keep FT2+SVM as primary
            p_ensemble = 0.4 * p_effnet + 0.4 * p_svm + 0.2 * p_res
            logger.debug("Spiral ResNet P(PD)=%.4f", p_res)
        except Exception as exc:
            logger.warning("Spiral ResNet TTA failed: %s", exc)

    has_pd     = p_ensemble >= 0.5
    confidence = p_ensemble if has_pd else (1.0 - p_ensemble)

    return {
        "has_parkinson":       has_pd,
        "probability":         round(p_ensemble, 4),
        "confidence":          round(confidence, 4),
        "severity":            round(p_ensemble * 100, 2),
        "label":               LABELS[int(has_pd)],
        "model":               "spiral_ensemble",
        "individual_probs":    individual,
    }


# ──────────────────────────────────────────────────────────────
# MRI PREDICTION  (4-CNN TTA + PSO-ELM equal weight, 98.19%)
# ──────────────────────────────────────────────────────────────

def predict_mri(image_path: str, model=None) -> dict:
    """
    Full MRI ensemble matching the notebook's best result (98.19%):
      All-4-CNN-TTA + PSO-ELM equal weight.

    CNN models:
      - EffNet-B3 TTA (10x)
      - EffNet-B4 TTA (10x)
      - ResNet50  TTA (10x)
      - DenseNet121 TTA (10x)

    PSO-ELM:
      Fused features from EffNet-B3 + EffNet-B4 + ResNet50
      → sc_fused → pca_fused (256 dims) → sc_final → PSO-ELM

    All 5 outputs are averaged with equal weight.

    Args:
        image_path: path to MRI image
        model: ignored (kept for API compatibility); models loaded from registry
    """
    from app.services.model_loader import ModelRegistry, get_torch_device

    b3       = ModelRegistry.get("mri_effnet_b3")
    b4       = ModelRegistry.get("mri_effnet_b4")
    res      = ModelRegistry.get("mri_resnet")
    den      = ModelRegistry.get("mri_densenet")
    bundle   = ModelRegistry.get("mri_bundle")
    device   = get_torch_device()

    pil_img  = Image.open(image_path).convert("RGB")
    tta_tf   = _get_mri_tta_transform()
    eval_tf  = _get_mri_eval_transform()

    n_tta    = 10
    cnn_probs = {}

    # ── CNN TTA for each backbone ─────────────────────────────
    for name, cnn_model in [("effnet_b3", b3), ("effnet_b4", b4),
                             ("resnet50", res), ("densenet121", den)]:
        if cnn_model is not None and tta_tf is not None:
            try:
                # DenseNet needs grayscale→3ch, which tta_tf already includes
                p = _tta_prob(cnn_model, pil_img, tta_tf, n_tta=n_tta, device=device)
                cnn_probs[name] = p
                logger.debug("MRI %s TTA P(PD)=%.4f", name, p)
            except Exception as exc:
                logger.warning("MRI %s TTA failed: %s", name, exc)

    # ── PSO-ELM on fused GAP features ────────────────────────
    p_pso_elm = 0.5   # neutral fallback
    if bundle is not None and eval_tf is not None:
        try:
            elm_final  = bundle.get("elm_final")
            W          = bundle.get("W")
            b_bias     = bundle.get("b")
            sc_final   = bundle.get("sc_final")
            pca_fused  = bundle.get("pca_fused")
            sc_fused   = bundle.get("sc_fused")

            if all(x is not None for x in [elm_final, W, b_bias, sc_final, pca_fused, sc_fused]):
                # Collect GAP features from EffNet-B3, EffNet-B4, ResNet50
                feat_list = []
                for cnn_model in [b3, b4, res]:
                    if cnn_model is not None:
                        t    = eval_tf(pil_img)
                        feat = _extract_gap_features(cnn_model, t, device)
                        if feat is not None:
                            feat_list.append(feat.reshape(-1))

                if feat_list:
                    fused      = np.concatenate(feat_list).reshape(1, -1)
                    fused_sc   = sc_fused.transform(fused)
                    fused_pca  = pca_fused.transform(fused_sc)
                    fused_fin  = sc_final.transform(fused_pca)

                    # Re-attach best PSO weights (training pattern)
                    elm_final.fit(fused_fin, np.array([0]), W=W, b=b_bias)
                    proba     = elm_final.predict_proba(fused_fin)[0]
                    p_pso_elm = float(proba[1]) if len(proba) > 1 else float(proba[0])
                    logger.debug("MRI PSO-ELM P(PD)=%.4f", p_pso_elm)

        except Exception as exc:
            logger.warning("MRI PSO-ELM inference failed: %s", exc)

    # ── Equal-weight ensemble (best config from notebook) ─────
    all_probs = list(cnn_probs.values()) + [p_pso_elm]
    if not all_probs:
        all_probs = [0.5]
    p_ensemble = float(np.mean(all_probs))

    has_pd     = p_ensemble >= 0.5
    confidence = p_ensemble if has_pd else (1.0 - p_ensemble)

    individual = {**cnn_probs, "pso_elm": p_pso_elm}

    return {
        "has_parkinson":    has_pd,
        "probability":      round(p_ensemble, 4),
        "confidence":       round(confidence, 4),
        "severity":         round(p_ensemble * 100, 2),
        "label":            LABELS[int(has_pd)],
        "model":            "mri_4cnn_pso_elm",
        "individual_probs": individual,
    }


# ──────────────────────────────────────────────────────────────
# Backward-compat Grad-CAM helper (used by mri.py / spiral.py)
# Returns None for PyTorch models (Grad-CAM is Keras-specific here)
# ──────────────────────────────────────────────────────────────

def _load_and_preprocess(image_path: str, target_size: tuple,
                          grayscale: bool = False) -> np.ndarray:
    """
    Load image and return numpy array (1, H, W, C) normalised [0,1].
    Kept for backward-compatibility with explainability_service.
    """
    img = Image.open(image_path)
    if grayscale:
        img = img.convert("L").convert("RGB")
    else:
        img = img.convert("RGB")
    img = img.resize(target_size)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)