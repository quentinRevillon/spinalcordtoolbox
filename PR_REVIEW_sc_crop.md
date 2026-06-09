# PR Review — Spatial cropping integration (sc-crop)

**Branch:** `feature/sc-crop-spinalcord` → `master`
**Files modified:** 6  |  **+260 lines  −23 lines**
**README modified:** no

---

## Affected commands

### `sct_deepseg spinalcord` — modified pipeline

The model switches from v3 (full-volume inference) to **v4 trained on cropped volumes**. SC crop is now applied automatically before inference; the prediction is restored to the full image space afterwards.

**Example call:**
```bash
sct_deepseg spinalcord -i sub-barcelona01_T2w.nii.gz
```

**Output files:**
```
sub-barcelona01_T2w_seg.nii.gz          ← segmentation (full image space, unchanged)
sub-barcelona01_T2w_cropbox.nii.gz      ← binary mask of the bounding box used
```

**FSLeyes command generated:**
```
fsleyes sub-barcelona01_T2w.nii.gz sub-barcelona01_T2w_seg.nii.gz -cm red -a 70 sub-barcelona01_T2w_cropbox.nii.gz -ot mask -mc 1 0 0 --outline -w 3 &
```
→ anatomical image + red segmentation + **red 3 px outline** of the bounding box

**New CLI options:**
```
-crop-mask FILE          box mask to use instead of automatic detection
-crop-pad-sup/inf MM     override superior/inferior padding (mm)
-crop-pad-left/right MM  override left/right padding
-crop-pad-ant/post MM    override anterior/posterior padding
```

---

### `sct_crop_image spinalcord` — new subcommand

Detects the spinal cord and crops the image without running segmentation.

**Example call:**
```bash
sct_crop_image spinalcord -i sub-barcelona01_T2w.nii.gz
```

**Output files:**
```
sub-barcelona01_T2w_crop.nii.gz         ← cropped volume (qform/sform origin updated)
sub-barcelona01_T2w_cropbox.nii.gz      ← binary mask of the bounding box
```

**FSLeyes command generated:**
```
fsleyes sub-barcelona01_T2w.nii.gz sub-barcelona01_T2w_crop.nii.gz -cm greyscale sub-barcelona01_T2w_cropbox.nii.gz -ot mask -mc 1 0 0 --outline -w 3 &
```
→ original image + cropped image + **red 3 px outline** of the bounding box

**New parameters added:** `-i`, `-o`, `-crop-pad-sup`, `-crop-pad-inf`, `-crop-pad-left`, `-crop-pad-right`, `-crop-pad-ant`, `-crop-pad-post`

---

## Changes per file and function

### `requirements.txt` `+2`
- Pin `sc-crop @ git+.../sc-crop.git@v0.4.1`

---

### `deepseg/models.py` `+52 / −11`
- Switch default `spinalcord` model URL to v4 release + add `"crop": True` opt-in flag `+8 / −2`
- Declare v3 model under a new name (own install folder, coexists with v4) `+13`
- Update `spinalcord` task description to mention sc-crop preprocessing `+3`
- Declare `spinalcord_v3` task, accessible via `sct_deepseg spinalcord_v3` `+15`
- Apply `keep_largest=1` default to `spinalcord_v3` as well `+1 / −1`

---

### `deepseg/inference.py` `+116 / −3`
- **`_bbox_from_mask()`** `NEW +14` — builds bbox from user mask (`-crop-mask`), validates shape + non-empty
- **`_cropbox_path()`** `NEW +5` — computes output path for the box mask
- **`_save_box_mask()`** `NEW +8` — saves bbox as a binary NIfTI mask
- **`_warn_if_cord_truncated()`** `NEW +42` — red warning if cord is truncated + green fix command with **automatic padding doubling** per affected face
- **`segment_nnunet()`** `MOD +34 / −3` — extended signature + crop block before inference + uncrop block after

  *Constants added:* `_DIR2PAD`, `_DIR2CLI`, `_DIR2PADKEY`, `_OPP`, `_SUGGEST_MM`

---

### `scripts/sct_deepseg.py` `+38 / −2`
- **`get_parser()`** `MOD +21` — `SPINAL CORD CROPPING` option group, shown only for models with `"crop": True`
- **`main()`** `MOD +17 / −2` — passes crop kwargs to `segment_non_ivadomed` + adds cropbox to FSLeyes display

---

### `utils/shell.py` `+5 / −1`
- **`IMTYPES_COLORMAP`** `MOD +1` — new `'cropbox'` entry
- **`_construct_fsleyes_syntax()`** `MOD +3 / −1` — special case for `cropbox` → `-ot mask -mc 1 0 0 --outline -w 3`

---

### `scripts/sct_crop_image.py` `+47 / −6`
- **`_main_spinalcord()`** `NEW +43` — parser + sc-crop detection + cropbox save + crop via `ImageCropper` + FSLeyes display
- **`main()`** `MOD +3 / −6` — dispatches to `_main_spinalcord()` if `argv[0] == 'spinalcord'`

---

## Planned refactoring — move helpers into sc_crop

The current PR duplicates three pieces of logic between `inference.py` and `sct_crop_image.py`.
Plan: move them into the sc_crop library (which Quentin owns), then simplify both SCT files.

---

### What moves into sc_crop

#### `sc_crop/cli.py` — detect mode now outputs NIfTI instead of txt

- `sc_crop -i t2.nii.gz` → `t2_cropbox.nii.gz` (filled binary mask, FSLeyes-ready) instead of `t2_bbox.txt`
- `--bbox` accepts both a NIfTI mask (reads non-zero extent) and a legacy `.txt` file
- Prints `fsleyes … -ot mask -mc 1 0 0 --outline -w 3` hint after detect
- Coordinates are already printed to stdout by `detect()` so no information is lost

#### `sc_crop/qc.py` — 2 new public functions

**`save_bbox_nifti(bbox, ref_nii, out_path)`** — save the crop box as a filled binary NIfTI mask.
- Currently duplicated verbatim: `_save_box_mask()` in `inference.py` and inline in `sct_crop_image.py`.
- After refactor both callers become: `sc_crop.save_bbox_nifti(bbox, img_nii, fname_cropbox)`.

**`check_seg_truncation(seg_nii, bbox)`** → `list[str]` — returns pad_* face names where the segmentation touches the crop boundary.
- Replaces the truncation detection loop inside `_warn_if_cord_truncated()`.
- Uses `bbox["original_axcodes"]` (already in the bbox dict) to map axes → anatomical faces, so the `orientation` parameter can be dropped from the caller.
- Reuses the `_FACE_MAP` constant already defined locally in `check_label_crop` (will be extracted to module level).

Also: extract `_FACE_MAP` dict as a module-level constant in `qc.py` so both `check_label_crop` and `check_seg_truncation` share it.

#### `sc_crop/__init__.py` — export the 2 new functions

```python
from .qc import ..., save_bbox_nifti, check_seg_truncation
```

---

### What changes in SCT after the refactor

#### `deepseg/inference.py` — simplification

| Before | After |
|---|---|
| `_DIR2PAD`, `_DIR2CLI`, `_DIR2PADKEY`, `_OPP` constants | removed (logic moves to sc_crop) |
| `_SUGGEST_MM` with direction-letter keys (`'S'`, `'I'`…) | kept, keys renamed to `pad_*` strings |
| `_PAD_TO_CLI` | added (maps `pad_superior` → `sup` etc.) |
| `_bbox_from_mask()` function (+14 lines) | kept as private helper (used once, not duplicated) |
| `_save_box_mask()` function (+8 lines) | removed → `sc_crop.save_bbox_nifti()` |
| `_warn_if_cord_truncated(seg_data, bbox, orientation, …)` (+42 lines) | simplified: orientation param dropped, body calls `sc_crop.check_seg_truncation()` then builds warning message (~20 lines) |

Expected net change for `inference.py`: **−~35 lines** (from +116 to ~+80).

#### `scripts/sct_crop_image.py` — minor cleanup

- Remove top-level `import numpy as np` (no longer needed in `_main_spinalcord`).
- Replace the 3-line inline bbox save block with `sc_crop.save_bbox_nifti(bbox, img_nii, fname_cropbox)`.
- Remove `import nibabel as nib` from inside `_main_spinalcord`.

Expected net change for `sct_crop_image.py`: **−~5 lines** (from +47 to ~+42).

---

## Remaining before upstream merge

- [ ] Move v4 model URL from personal fork to official `sct-pipeline` repository
- [ ] Implement refactoring above in sc_crop, then update SCT
- [ ] Add CLI tests for the crop pipeline (`testing/cli/test_sct_deepseg.py`)
- [ ] Add entry in `CHANGES.md`
