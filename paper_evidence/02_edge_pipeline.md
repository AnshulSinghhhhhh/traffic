# 02 — Edge Pipeline Specification & Hyperparameters

**Document Status**: COMPLETED  
**Verification Date**: 2026-09-29  
**Source Files**: `ml/detect.ipynb`, `idahr_plate_detector.pt`, `ocr_enhancements.py`, `dvla_area_codes.py`  

---

## 1. Machine Learning Models & Weights

### 1.1 Vehicle Detection Model
- **Architecture**: Ultralytics YOLOv8 Nano (`yolov8n.pt`).
- **Framework & Version**: Ultralytics `8.3.40` (`ultralytics==8.3.40` in `ml/detect.ipynb` Cell 4).
- **Pretrained Weights**: Pretrained on COCO dataset (80 object classes).
- **Target Filtered Classes**:
  - Class `2`: `"car"`
  - Class `3`: `"motorcycle"`
  - Class `5`: `"bus"`
  - Class `7`: `"truck"`
- **Detection Confidence Threshold**: `VEHICLE_CONF_THRESHOLD = 0.40` (raised from 0.35 in Cell 10 to suppress marginal false positives).
- **Execution Target**: Single forward pass per sampled frame.

### 1.2 License Plate Detection Model (`idahr_plate_detector.pt`)
Extracted directly from binary checkpoint metadata via `torch.load('idahr_plate_detector.pt', weights_only=False)`:
- **Base Architecture**: YOLOv8 Nano (`yolov8n.pt`).
- **Ultralytics Version at Training**: `8.3.40`.
- **Training Completion Date**: `2026-08-23T17:36:13.523787` (`FOUND`).
- **Software License**: AGPL-3.0 (`FOUND` in checkpoint `license` field).
- **Single Target Class**: Class `0`: `"License_Plate"` (`nc = 1`).
- **Training Dataset**:
  - Source Path: `/content/License-Plate-Recognition-4/data.yaml` (`FOUND` in checkpoint `train_args['data']`).
  - Origin: Roboflow Universe dataset `License-Plate-Recognition-4`.
  - Dataset Size: **MISSING** (Exact image counts for train/val splits were located in Google Colab ephemeral disk and are not recorded inside the checkpoint dictionary. To find the training log, inspect Google Drive Colab output logs from August 23, 2026, or query the Roboflow Universe API for `License-Plate-Recognition-4`).
- **Training Hyperparameters**:
  - Epochs: `15` (`FOUND` in `train_args['epochs']`, total training wall-clock time `5842.81 s` / 97.38 min across 15 epochs).
  - Input Image Resolution: `imgsz = 640` ($640 \times 640$ pixels).
  - Batch Size: `16`.
  - Optimization Algorithm: `optimizer = 'auto'` with SGD momentum ($lr_0 = 0.01$, $lr_f = 0.01$, $\text{momentum} = 0.937$, $\text{weight\_decay} = 0.0005$).
  - Warmup: 3.0 epochs.
- **Empirical Validation Metrics at Epoch 15** (`FOUND` in checkpoint `train_metrics`):
  - **Precision ($B$)**: `0.97796` (**97.80%**)
  - **Recall ($B$)**: `0.95723` (**95.72%**)
  - **$\text{mAP}_{50}$ ($B$)**: `0.98147` (**98.15%**)
  - **$\text{mAP}_{50-95}$ ($B$)**: `0.69225` (**69.23%**)
  - **Validation Box Loss**: `1.12839`
  - **Validation Class Loss**: `0.41780`
  - **Validation DFL Loss**: `1.16172`
  - **Combined Model Fitness**: `0.72118`

### 1.3 Optical Character Recognition (OCR) Engine
- **Engine**: PaddleOCR `3.7.0` (`pip install paddleocr==3.7.0`).
- **Runtime Backend**: PaddlePaddle GPU `3.3.1` (cu126 wheel: `paddlepaddle_gpu-3.3.1-cp312-cp312-linux_x86_64.whl`).
- **Model Preset**: `PP-OCRv4` (`lang="en"`, `ocr_version="PP-OCRv4"`, `device="gpu"` in Cell 16).
- **Backbone Architecture**: SVTR / MobileNet-v3 with Connectionist Temporal Classification (CTC).
- **Execution Strategy**: Dual-pass execution on both the raw plate crop and a preprocessed crop (see § 3); selects the reading with the higher recognition confidence score.

### 1.4 Object Tracker Implementation (SORT)
A custom Python implementation of Simple Online and Realtime Tracking (SORT) is embedded in `ml/detect.ipynb` Cell 8:
- **State Representation**: 7-dimensional Kalman state vector:
  $$\mathbf{x} = [u, v, s, r, \dot{u}, \dot{v}, \dot{s}]^T$$
  where $u, v$ represent horizontal and vertical bounding box center coordinates, $s$ is box scale (area), and $r$ is aspect ratio ($w/h$).
- **Motion Model**: Constant velocity linear dynamical system with diagonal covariance matrices.
- **Data Association**: Hungarian algorithm (Munkres) on a cost matrix of negative Intersection-over-Union ($-IoU$).
- **Configured Parameters** (`FOUND` in Cell 10):
  - `SORT_MAX_AGE = 12`: Maximum consecutive missed frames before a track is dropped (loosened from classic 1 to survive occlusion).
  - `SORT_MIN_HITS = 2`: Minimum detections required before a track is confirmed and emitted.
  - `SORT_IOU_THRESHOLD = 0.20`: Minimum spatial overlap required for Kalman track association.

---

## 2. Pipeline Hyperparameters & Quality Gates

| Parameter Name | Value | Code Location | Functional Purpose |
|---|---|---|---|
| `SAMPLE_FPS` | `5` | `detect.ipynb:10` | Video subsampling rate. For 30 FPS video, processes 1 frame every 6 frames ($16.67\%$ duty cycle). |
| `VEHICLE_CONF_THRESHOLD` | `0.40` | `detect.ipynb:10` | Minimum YOLOv8 confidence score to initiate a vehicle track. |
| `PLATE_DET_CONF` | `0.25` | `detect.ipynb:10` | Minimum confidence score for plate detection bounding boxes. |
| `PLATE_BBOX_PADDING` | `4 px` | `detect.ipynb:18` | Symmetrical margin added to plate bounds (`x1-4, y1-4, x2+4, y2+4`) to avoid clipping edge characters. |
| `MIN_PLATE_AREA_PX` | `900 px` | `detect.ipynb:10` | Discards candidate plate crops smaller than $30 \times 30\text{ px}$, preventing illegible OCR invocations. |
| `MIN_VEHICLE_AREA_FOR_PLATE_PX` | `4000 px` | `detect.ipynb:10` | Bypasses plate detection on vehicles smaller than $\approx 63 \times 63\text{ px}$. |
| `MAX_OCR_ATTEMPTS_PER_TRACK` | `8` | `detect.ipynb:10` | Hard cap on total OCR forward passes per track across its lifetime to prevent runaway computation. |
| `OCR_STOP_CONF_THRESHOLD` | `0.90` | `detect.ipynb:10` | Early-exit threshold: once a track yields combined confidence $\ge 0.90$, further OCR calls are suppressed. |
| `OCR_CONF_FLAG_THRESHOLD` | `0.55` | `detect.ipynb:10` | Audit threshold: emitted reads with combined confidence $< 0.55$ are tagged for human operator review. |
| `ACTIVE_PLATE_FORMAT` | `"UK"` | `detect.ipynb:10` | Active regex and dictionary dispatch switch (`"UK"` or `"INDIA"`). |

---

## 3. Image Preprocessing, CLAHE & Denoising Settings

Plate crops undergo deterministic preprocessing in `preprocess_plate()` (`detect.ipynb` Cell 18) before secondary OCR evaluation:

1. **Bicubic Dynamic Upscaling**:
   - `scale = max(1.0, 200.0 / max(h, 1))`
   - If plate height $h < 200\text{ px}$, the crop is upscaled via `cv2.resize(..., interpolation=cv2.INTER_CUBIC)`.
2. **Grayscale Conversion**:
   - `gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)`
3. **Contrast-Limited Adaptive Histogram Equalization (CLAHE)**:
   - `clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))`
   - Enhances local character contrast while suppressing background noise amplification.
4. **Sharpness-Gated Fast Non-Local Means Denoising**:
   - Heuristic (`needs_denoising`):
     - Laplacian variance: $\text{Var}(\nabla^2 I) < 100$ (indicates low edge sharpness)
     - Standard deviation: $\sigma(I) < 50$ (indicates low character-background contrast)
   - When True: Calls `cv2.fastNlMeansDenoising(contrast, h=10)` ($h$ luminance filter strength $= 10$).
   - When False: Denoising is bypassed, saving $\sim 250\text{ ms}$ of CPU processing per crop.
5. **Adaptive Binarization**:
   - `cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 10)`
   - Computes local threshold as Gaussian-weighted sum of $25 \times 25$ neighborhood minus constant $C = 10$.

---

## 4. Character-Confusion Correction Rules & Templates

Optical confusion normalization is implemented in `normalize_plate()` (`detect.ipynb` Cell 18) and expanded in `ocr_enhancements.py`:

### 4.1 Positional Substitution Dictionaries
- **Character to Digit** (`CHAR_TO_DIGIT`):
  `{"O": "0", "I": "1", "Z": "2", "A": "4", "S": "5", "G": "6", "B": "8", "Q": "0", "T": "7", "D": "0"}`
- **Digit to Character** (`DIGIT_TO_CHAR`):
  `{"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "8": "B", "7": "T"}`

### 4.2 Positional Templates by Plate Standard
- **United Kingdom (`ACTIVE_PLATE_FORMAT = "UK"`)**:
  - Length 7: `LLDDLLL` (2 letters: Area Code, 2 digits: Age Identifier, 3 letters: Random Suffix).
  - Validation Regex: `^[A-Z]{2}[0-9]{2}[A-Z]{3}$`.
  - Disallowed Characters in UK standard: `I` and `Q` are banned from all positions; `Z` is banned from the first two positions.
  - Position 0 & 1 (`L`): Replaces digits via `DIGIT_TO_CHAR`. In addition, `I -> L`, `Q -> O`, and leading `Z -> S`.
  - Position 2 & 3 (`D`): Replaces alphabetic characters via `CHAR_TO_DIGIT`.
  - Position 4, 5, 6 (`L`): Replaces digits via `DIGIT_TO_CHAR`.
- **India (`ACTIVE_PLATE_FORMAT = "INDIA"`)**:
  - Length 9: `LLDDLDDDD` (e.g., `DL01A1234`).
  - Length 10: `LLDDLLDDDD` (e.g., `KA05MH1234`).
  - Length 11: `LLDDLLLDDDD` (e.g., `MH12ABC1234`).
  - Validation Regex: `^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$`.
  - Position 0 & 1 (`L`): Evaluated against the 36-entry `INDIAN_STATE_CODES` whitelist.

### 4.3 Structural Artifact Stripping
- **Duplicate Prefix Shadow Stripping**: Front bumper shadow lines occasionally produce phantom leading characters. If string length is 8 and characters 0 and 1 are identical (`text[0] == text[1]`), candidate `text[1:]` is validated against the DVLA whitelist. If valid, the artifact is stripped (e.g., `DDU06XRO -> DU06XRO`).

---

## 5. DVLA Local Memory Tag Whitelist Provenance

### 5.1 Source & Extraction
- **Authoritative Source**: Extracted from the official Driver and Vehicle Licensing Agency (DVLA) local memory tag specification (2001 to Present), documented under Wikipedia article *Vehicle registration plates of the United Kingdom* (pageid `36602200`).
- **Extraction Artifact**: Saved locally in [section6_wikitext.json](file:///c:/Users/anshu/Documents/newstart/Traffic/section6_wikitext.json) and compiled via `scratch_uk_tags.py` into [dvla_area_codes.py](file:///c:/Users/anshu/Documents/newstart/Traffic/dvla_area_codes.py).
- **Total Registered Tags**: **451 valid two-letter prefixes** covering 20 official geographic regions (e.g., `AA`–`AY` Anglia, `BA`–`BY` Birmingham, `CA`–`CY` Cymru/Wales, `LA`–`LY` London, `WA`–`WY` West of England).

### 5.2 Bounded Tag Correction Algorithm (`correct_uk_area_code`)
If the two-letter prefix does not exist in `UK_AREA_CODES`, the bounded normalizer searches for the minimum-cost replacement among confusion sets:
- Cost Function: Substitution from `LETTER_CONFUSIONS` incurs penalty $1.0$; arbitrary letter distance incurs penalty $2.0$.
- Decision Threshold: If a valid DVLA tag exists with $\text{cost} \le 2.5$, the prefix is replaced. Otherwise, the raw reading is preserved to avoid false hallucinated area codes.
