"""
Best-frame composite scoring + auto-color extraction for SAM2 video propagation tracks.

Isolated from sam2_video.py so it can be unit-tested without a SAM2 model loaded.

Inputs are plain numpy arrays (frames as BGR uint8, masks as uint8 0/255).
Outputs are floats and string color labels — no DB access here.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
DEFAULT_MAX_DETECTION_CROP_BYTES = 2000000

@dataclass
class ScoringConfig:
    """All weights and thresholds for best-frame composite scoring.

    Loaded from config.yaml [tracks] section by sam2_video.py and passed in.
    Defaults match the values in config.yaml.example.
    """
    weight_iou: float = 0.4
    weight_area: float = 0.2
    weight_sharpness: float = 0.4
    weight_edge_penalty: float = 0.3
    weight_center_prior: float = 0.05
    target_area_norm: float = 0.005
    target_area_sigma: float = 0.01
    min_mask_pixels_for_sharpness: int = 50
    min_mask_pixels_to_score: int = 100

def laplacian_sharpness(frame_bgr: np.ndarray, mask: np.ndarray, min_pixels: int=50) -> float:
    """Variance of Laplacian on the masked crop (higher = sharper).

    Crop to the mask's bounding box first so background blur doesn't dilute the score.
    Returns 0.0 if the mask has fewer than `min_pixels` — variance on tiny patches is
    dominated by single-pixel noise and produces wildly unreliable values.
    """
    ...

def area_score_from_pixels(mask_pixels: int, frame_shape: Tuple[int, int], cfg: ScoringConfig) -> float:
    """Gaussian around target_area_norm, given only the mask's pixel COUNT.

    Split out from `area_score` so a caller that already knows the count (and
    the frame's shape) never has to keep the full-frame mask alive just to call
    `.sum()` on it again. Same arithmetic, same float: the count is the only
    thing `area_score` ever read out of the mask.
    """
    ...

def area_score(mask: np.ndarray, frame_shape: Tuple[int, int], cfg: ScoringConfig) -> float:
    """Gaussian around target_area_norm. 1.0 at target, decays away.

    Avoids `log(area)` divergence for tiny/empty masks and unbounded reward for huge masks.
    """
    ...

def border_touch_penalty(mask: np.ndarray, edge_px: int=2) -> float:
    """1.0 if the mask touches the image border, else 0.0.

    Border-touching detections are usually partial / about to leave frame.
    """
    ...

def center_frame_prior(mask: np.ndarray) -> float:
    """1 - normalized distance from mask centroid to image center.

    Underwater / GoPro footage tends to be sharper + better-lit at center.
    """
    ...

def score_detection(frame_bgr: np.ndarray, mask: np.ndarray, sam2_score: float, max_sharpness_in_track: float, cfg: ScoringConfig, *, mask_pixels: Optional[int]=None, frame_shape: Optional[Tuple[int, int]]=None, edge_penalty: Optional[float]=None, center_prior: Optional[float]=None, sharpness_raw: Optional[float]=None) -> Dict[str, float]:
    """Compute composite score + sub-scores for a single detection.

    Sharpness is normalized PER-TRACK (passed in as max), not globally.
    Caller is responsible for two-pass scoring: first pass collects raw sharpness values,
    second pass computes composites with the per-track max.

    Masks smaller than cfg.min_mask_pixels_to_score are REJECTED — composite returned
    as -inf so they can never win pick_best_frame. These usually indicate propagation
    collapse / partial occlusion and shouldn't even reach scoring, but we're defensive.

    `frame_bgr` / `mask` may be a PADDED CROP around the mask rather than the whole
    frame (see `make_scoring_context`). Everything sharpness needs is inside that
    crop, but the three geometry sub-scores are defined against the FRAME, so they
    are passed in precomputed via the keyword-only arguments instead — measured on
    the full mask at production time, by these same functions, before the frame was
    dropped. Omit them and the legacy full-frame behaviour is unchanged.
    """
    ...

def _color_context_padding(mask_pixels: int, bb_w: int, bb_h: int) -> int:
    """How far outside the mask's bbox the scoring/colour code actually reaches.

    THESE TWO LINES MIRROR `extract_auto_color` AND MUST TRACK IT. That function
    is the only consumer that looks at pixels *outside* the mask:

      * it DILATES the mask by `dilate_n` and samples the ring that appears —
        so the crop must contain everything within `dilate_n` of the bbox, or
        the skin baseline is computed from a truncated ring;
      * it ERODES the mask by `erosion_n`, and `cv2.erode` treats pixels outside
        the array as SET (`morphologyDefaultBorderValue`). A crop cut flush to
        the mask bbox would therefore refuse to erode at its own edge, whereas
        the full frame erodes there against real zeros. The pad supplies those
        zeros, so the erosion is identical.

    `+ 1` is slack, not superstition: it costs a single pixel ring and keeps the
    crop correct if either kernel is ever rounded up rather than down.

    `tests/test_propagation_memory.py` asserts crop-vs-full equality on random
    masks, so if `extract_auto_color`'s neighbourhood grows and this does not,
    that test fails rather than the auto-colour silently changing.
    """
    ...

def make_scoring_context(frame_bgr: np.ndarray, mask: np.ndarray, *, sharpness_min_pixels: int=ScoringConfig.min_mask_pixels_for_sharpness, max_crop_bytes: Optional[int]=None) -> Dict:
    """Reduce (full frame, full-frame mask) to everything scoring will ever need.

    A propagation holds every detection in one list until scoring finishes, so
    whatever a detection carries is multiplied by the detection count. Carrying
    the frame cost 8.29 MB per detection at 1080p — 1,003.6 MB for a default
    ±60-frame window.

    Be precise about the concurrent ceiling, because the obvious reading is wrong
    by ~5x: `tracks.max_concurrent_propagations` is checked at ENQUEUE against
    `count_active_propagations(email)`, so it caps a user's pending track ROWS,
    not concurrent CPU work. Actual propagation runs on one module-level queue
    and a single worker thread per Gunicorn process, further serialized by
    `_sam2_video_lock`. With WORKERS=4 the box-wide ceiling is ~4 concurrent
    propagations (~4 GB before this change), NOT one per student. Still worth
    fixing; just do not quote a 20-student figure.

    What survives instead:
      * `frame_crop` / `mask_crop` — the mask's bbox plus `_color_context_padding`,
        COPIED (a numpy slice is a view and would pin the whole frame alive).
        Sharpness and auto-colour read only this neighbourhood.
      * `frame_shape`, `mask_pixels` — the frame's dimensions and the mask's
        pixel count, which is all `area_score` ever read off the mask.
      * `edge_penalty`, `center_prior` — computed HERE, by the same functions,
        on the real full-frame mask. They are frame-relative, so deriving them
        later from a crop would mean re-deriving the arithmetic; measuring them
        while the mask is still whole makes them exact by construction instead.
      * `sharpness_raw` — the LAST thing scoring needed pixels for. It is
        computed here, off the crop that is in hand anyway, with the min-pixels
        value THREADED IN from the caller's ScoringConfig (never hardcoded, or
        a re-tuned config would silently score against the old threshold).
        `sharpness_min_pixels` records which value was used so `two_pass_score`
        can refuse a stale one rather than quietly mixing thresholds.

    With sharpness precomputed, NOTHING in the scoring path reads pixels any
    more — the crop survives only so `extract_auto_color` can read the single
    BEST detection once scoring has picked it. That is what makes it droppable:
    `max_crop_bytes` caps what one detection may hold, and over that ceiling the
    crop is not stored at all (`crop_omitted`). `crop_box` + the detection's own
    `frame_number` / `mask_rle` are then enough to rebuild the exact same two
    arrays for whichever ONE detection turns out to be the best
    (`sam2_video.rebuild_scoring_pixels`). `max_crop_bytes=None` means no
    ceiling, which is the historical behaviour and what direct callers get.
    """
    ...

def detection_pixels(d: Dict) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """The (frame-ish, mask-ish) pair to score `d` from — crop if present, else legacy.

    Returns (None, None) ONLY for a detection that declined to keep its crop on
    budget grounds, which says so explicitly via `crop_omitted`. Every caller of
    this function must treat that as "rebuild them or do without", never as
    "score from nothing" — `two_pass_score` no longer needs pixels at all, and
    `propagate_and_score` re-reads the frame for the one detection that does.

    Raises KeyError when a detection carries NEITHER pair AND has not declared
    the omission. Before the crop refactor this lookup was `d["frame_bgr"]`, so
    a malformed detection failed loudly; going through `.get()` would instead
    hand `laplacian_sharpness` (None, None), which returns 0.0 and silently
    corrupts the best-frame ranking — a wrong track preview and a wrong
    auto-colour, with no error. A missing pair is a programming error, so keep
    it loud; a DECLARED omission is not one.
    """
    ...

def pick_best_frame(detections: List[Dict]) -> Optional[Dict]:
    """Return the detection with the highest composite_score, or None if empty."""
    ...

@dataclass
class ColorConfig:
    """LAB-delta thresholds for binning auto-extracted color.

    Loaded from config.yaml [tracks] section.
    """
    pink_l_min: float = -10.0
    pink_chroma_min: float = 8.0
    white_l_min: float = 12.0
    black_l_max: float = -25.0
    grey_l_band: float = 8.0
    grey_chroma_max: float = 5.0
    show_prediction_threshold: float = 0.5
    severity_min_fraction: float = 0.1

def _classify_pixel(l_delta: float, a_delta: float, chroma: float, cfg: ColorConfig) -> str:
    """Map a single pixel's LAB delta (vs skin ring) to one of 5 colors.

    Order of checks matters when bins overlap — we put BLACK first because a
    very-dark + neutral-chroma pixel could match GREY's |L| band, but the
    biological reality (fresh trauma) is BLACK.
    """
    ...

def describe_color_delta(delta_l: Optional[float], delta_a: Optional[float]=None) -> Optional[str]:
    """The measurement in words, for a human who is about to name a colour.

    Deliberately NOT a colour name: naming it is the labeler's job, and the whole
    point of showing the number is that the name is a convention laid over it.
    "Just perceptible" is the ~2.3 L* JND, below which a lightness difference is
    not something a human is failing to see.
    """
    ...

def extract_auto_color(frame_bgr: np.ndarray, mask: np.ndarray, cfg: ColorConfig) -> Tuple[Optional[str], float, Dict]:
    """Compute predicted scar color via per-pixel severity-ranked histogram.

    Why histogram, not median:
      Earlier versions took the median LAB delta of all mask pixels and binned
      that single value. On heterogeneous scars (e.g. fresh black core + pink
      healing edges) the median averaged out to GREY — every verified track
      auto-coded GREY while humans picked PINK / WHITE / BLACK. The bias was
      strong (6/6 verified tracks disagreed).

    Why we erode the mask:
      For the bbox tracker, "mask" is a filled rectangle of the scar bbox. The
      bbox necessarily includes a border of surrounding skin. Counting those
      skin pixels in the histogram dilutes the signal — earlier results showed
      75-94% GREY because most of the bbox was just skin. We erode the mask
      inward by ~20% on each side so the inner core (where the actual scar
      tissue lives) dominates the histogram.

    Algorithm:
      1. Erode the mask by erosion_pixels to remove the outer band of skin
         that the bbox tracker inevitably includes.
      2. Skin-ring LAB: dilate the ORIGINAL mask, take ring = dilated - original.
         Median LAB of ring (after dropping top-5% L* highlights) approximates
         surrounding skin color. Use the original mask for the ring so the
         skin baseline is computed from real surrounding skin, not the bbox
         interior.
      3. For each pixel in the ERODED mask: LAB delta vs ring → classify into
         BLACK / PINK / WHITE / GREY / OTHER via cfg thresholds.
      4. Walk SEVERITY_ORDER (BLACK > PINK > WHITE > GREY > OTHER). Return the
         first color whose pixel fraction ≥ cfg.severity_min_fraction (default
         10%). This biases auto-color toward CLINICALLY SIGNIFICANT colors —
         a scar with 30% black + 60% pink correctly returns BLACK, not PINK.
      5. Confidence = winning color's pixel fraction (so a 70% match reads as
         0.7, a 12%-just-above-threshold as 0.12).

    Returns (color_label_or_None, confidence_0_to_1, debug_dict). Returns
    (None, 0.0, {...}) if mask or ring is too small to be reliable.

    `frame_bgr`/`mask` may be a padded CROP rather than a whole frame — every
    read here is either inside the mask or inside the dilated ring around it,
    both of which `_color_context_padding` guarantees the crop contains. If the
    dilation or erosion neighbourhood here changes, change that function too.
    """
    ...

def two_pass_score(raw_detections: List[Dict], cfg: ScoringConfig) -> List[Dict]:
    """Re-rank a set of detections in-place using per-track sharpness normalization.

    raw_detections: list of dicts each containing at minimum:
      - the pixels to score from, as EITHER the compact pair written by
        `make_scoring_context` ('frame_crop' / 'mask_crop', plus 'frame_shape',
        'mask_pixels', 'edge_penalty', 'center_prior'), OR the legacy full-frame
        pair ('frame_bgr' / 'mask'). Both are transient, neither is persisted.
      - 'sam2_score' (float)
      - 'frame_number' (int)
      - 'bbox' (dict)

    This function is why the retention mattered: it runs over the COMPLETE list
    twice, so every detection's pixels are alive simultaneously.

    It no longer reads pixels at all when the detections came from
    `make_scoring_context`. Pass 1 existed only to collect raw sharpness for the
    per-track normalization, and sharpness is now measured at PRODUCTION time,
    while the frame is in hand, off the very crop this used to re-read. That is
    what lets a detection drop its crop and still score identically: with
    `sharpness_raw`, `mask_pixels`, `frame_shape`, `edge_penalty` and
    `center_prior` all precomputed, `score_detection` touches neither array.

    A stored sharpness is only reused when it was measured against the SAME
    `min_mask_pixels_for_sharpness` this call is configured with. Reusing a
    value computed under a different threshold would silently mix two scoring
    regimes in one track; if the pixels are still around we recompute, and if
    they are not we refuse rather than guess.

    After this call, each dict has the additional fields from score_detection().
    """
    ...
