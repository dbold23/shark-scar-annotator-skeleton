"""Stream A (re-ID) — embedding extractors for individual re-identification.

This module supplies the real extractors that Phase A1 turns on. It is **import-safe with
no heavy deps installed** (torch / timm / transformers / wildlife-tools are imported lazily,
only when an extractor actually loads), so the app imports cleanly when re-ID is OFF.

Model choice (verified research — plans/01-research-models-reid.md §4a/§5):
  - `miewid`         MiewID-msv3 (Conservation X Labs / WildMe) — purpose-trained animal re-ID,
                     2152-dim, ~78% avg Top-1, beats MegaDescriptor on unseen species. RECOMMENDED.
  - `wildfusion`     Calibrated fusion of foundation embeddings (MegaDescriptor-L-384 + DINOv2);
                     SOTA zero-shot. At A1 we store the *foundation-embedding component*; the
                     pairwise local-feature matchers (LoFTR/LightGlue) are layered in at MATCH
                     time (A2), since they are not a single storable vector. RECOMMENDED (zero-shot).
  - `megadescriptor` MegaDescriptor-L-384 (Swin) — first animal re-ID foundation model; a baseline
                     MiewID/WildFusion surpass. NOTE: MegaDescriptor-L is CC-BY-NC-4.0 (non-commercial).
  - `dinov2`         DINOv2-small CLS token (384-dim). VERIFIED WEAKEST for fine-grained ID — kept
                     only as a fusion input / baseline. **Never the default; do not use as primary.**
  - `hashstub`       Deterministic NON-real placeholder (downsampled-image vector, no ML deps). For
                     pipeline smoke-tests / CI only — every vector is tagged `hashstub_v1` so the
                     matcher (A2) can refuse it. NOT a real embedding.

Signature construction (build_signature): fins / body-pattern are the PRIMARY signal and scars are
only corroborating (verified: scars are an UNPROVEN re-ID cue — they change and heal). The PRIMARY
vector embeds a body-scale region (`region=full|padded_scar|scar`); the tight scar crop is stored
separately as `scar_vec` (SECONDARY). The payload is self-describing (carries its own model tag) so
embeddings from different models are never silently compared.

Weights are lazy-loaded and cached under `reid.embeddings.weights_dir` (default models/reid/,
gitignored), mirroring how pose/SAM2 weights are handled. Install the stack for your chosen model:
    miewid / wildfusion / megadescriptor : pip install timm transformers torch  (+ wildlife-tools for wildfusion local matchers, A2)
    dinov2                               : pip install transformers torch
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
PAYLOAD_VERSION = 1
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)

class ExtractorUnavailable(RuntimeError):
    """Raised when a selected extractor's deps or weights aren't available.

    The backfill job catches this at startup and reports it as a clean error
    (rather than failing per-track), so a missing ML stack never half-fills the DB.
    """

def _torch():
    ...

def _resolve_device(device: str):
    ...

def _to_tensor(image_bgr: np.ndarray, size: int, device):
    """BGR uint8 HxWx3 → normalized CHW float tensor (1,3,size,size) on `device`."""
    ...

def _l2(vec: np.ndarray) -> np.ndarray:
    ...

class _BaseExtractor:
    dim: int = 0

    def embed(self, image_bgr: np.ndarray) -> np.ndarray:
        ...

class _HashStubExtractor(_BaseExtractor):
    """Deterministic, dependency-free placeholder — NOT a real embedding.

    Vector = L2-normalized 16x16 grayscale of the crop (256 dims). Same crop → same
    vector (so backfill is idempotent and distinct crops are distinguishable), but it
    encodes nothing learned. Tagged `hashstub_v1` so A2 can hard-refuse it.
    """
    dim = 256

    def embed(self, image_bgr: np.ndarray) -> np.ndarray:
        ...

class _TimmExtractor(_BaseExtractor):
    """timm hf-hub backbone with the classifier head removed (MegaDescriptor, etc.)."""

    def __init__(self, model_tag: str, hf_id: str, size: int, device: str, weights_dir: Optional[str]):
        ...

    def embed(self, image_bgr: np.ndarray) -> np.ndarray:
        ...

class _HFAutoModelExtractor(_BaseExtractor):
    """transformers AutoModel extractor (MiewID via trust_remote_code, or DINOv2 CLS token)."""

    def __init__(self, model_tag: str, hf_id: str, size: int, device: str, weights_dir: Optional[str], *, trust_remote_code: bool, cls_token: bool):
        ...

    def embed(self, image_bgr: np.ndarray) -> np.ndarray:
        ...

    def _extract(self, out):
        ...

class _WildFusionExtractor(_BaseExtractor):
    """A1 storable component of WildFusion: concat(MegaDescriptor-L-384, DINOv2-small), renormalized.

    The full WildFusion adds calibrated local-feature matchers (LoFTR/LightGlue via wildlife-tools)
    at MATCH time — that is an A2 concern (pairwise, not a stored vector). Here we persist the
    foundation-embedding part so the gallery is ready for that re-ranking.
    """

    def __init__(self, device: str, weights_dir: Optional[str]):
        ...

    def embed(self, image_bgr: np.ndarray) -> np.ndarray:
        ...

def get_extractor(model: str, device: str='cpu', weights_dir: Optional[str]=None) -> _BaseExtractor:
    """Return a cached extractor for (model, device, weights_dir).

    Raises ExtractorUnavailable if the model's deps/weights can't be loaded.
    `model` is one of: miewid | wildfusion | megadescriptor | dinov2 | hashstub.
    """
    ...

def _set_hf_cache(weights_dir: str) -> None:
    """Point HF/torch model caches at the gitignored weights_dir (best-effort)."""
    ...

def _crop_region(frame_bgr: np.ndarray, scar_bbox, region: str, padded_scar_frac: float):
    """Return the PRIMARY crop for `region`. None if it degenerates to too-small."""
    ...

def _scar_crop(frame_bgr: np.ndarray, scar_bbox):
    ...

def build_signature(frame_bgr: np.ndarray, scar_bbox: Optional[Tuple[int, int, int, int]], extractor: _BaseExtractor, *, region: str='full', include_scar_vec: bool=True, padded_scar_frac: float=2.0) -> Optional[Dict]:
    """Build the self-describing signature payload for one best-frame + scar bbox.

    PRIMARY `vec` = embedding of the body-scale `region` crop (fins/body — the proven signal).
    SECONDARY `scar_vec` = embedding of the tight scar crop (corroboration only), when
    include_scar_vec and region != 'scar'. Returns None if the primary crop is unusable.
    """
    ...
