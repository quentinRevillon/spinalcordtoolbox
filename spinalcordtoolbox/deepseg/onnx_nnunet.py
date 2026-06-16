"""
ONNX inference backend for nnUNet-trained models.

Runs nnUNet inference through onnxruntime only (no PyTorch / nnunetv2 at inference time), using the
`model.onnx` produced at install time by `models._export_onnx`. This is the default backend for
`sct_deepseg spinalcord`; pass `-backend nnunet` to use the original PyTorch predictor instead.

The actual preprocessing + sliding-window + postprocessing is delegated to `nnunet_onnx.infer_onnx`
(reorients to RPI internally, restores the input orientation). Binary (single-class) models only —
see https://github.com/quentinRevillon/nnunet-onnx/issues/1.

Copyright (c) 2024 Polytechnique Montreal <www.neuro.polymtl.ca>
License: see the file LICENSE
"""

import glob
import json
import os


def find_onnx_model(path_model):
    """Return the path to the `model.onnx` produced at install time, or raise if missing."""
    matches = glob.glob(os.path.join(path_model, "**", "model.onnx"), recursive=True)
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one 'model.onnx' under model path {path_model}, found {len(matches)}. "
            f"Reinstall the model with `sct_deepseg ... -install`, or use `-backend nnunet`.")
    return matches[0]


class OnnxModel:
    """Lightweight predictor holder for the ONNX backend (mirrors the role of `nnUNetPredictor`)."""
    def __init__(self, onnx_path, dataset_json):
        self.onnx_path = onnx_path
        self.dataset_json = dataset_json


def create_onnx_session(path_model, device, **kwargs):
    """Locate `model.onnx` + its `dataset.json`. Signature mirrors `nnunet.create_nnunet_from_plans`.

    `device` and any extra network kwargs (e.g. `test_time_aug`) are accepted for signature
    compatibility but unused: the ONNX backend runs single-fold on CPU.
    """
    onnx_path = find_onnx_model(path_model)
    with open(os.path.join(os.path.dirname(onnx_path), "dataset.json")) as f:
        dataset_json = json.load(f)
    return OnnxModel(onnx_path, dataset_json)
