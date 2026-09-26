import json
from pathlib import Path

with open('dvla_area_codes.py', 'r', encoding='utf-8') as f:
    dvla_code = f.read().strip()

def update_notebook(path):
    with open(path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    # Cell 18: UK_AREA_CODES and ocr_plate_crop
    c18_text = ''.join(nb['cells'][18]['source'])
    idx1 = c18_text.find('UK_AREA_CODES = {')
    idx2 = c18_text.find('}', idx1)
    if idx1 != -1 and idx2 != -1:
        c18_text = c18_text[:idx1] + dvla_code + c18_text[idx2+1:]
    
    old_ret = '    return {\n        "text": corrected_text,\n        "combined_conf": round(det_conf * ocr_conf, 3),\n        "was_corrected": was_corrected,\n    }'
    new_ret = '    return {\n        "text": corrected_text,\n        "combined_conf": round(det_conf * ocr_conf, 3),\n        "was_corrected": was_corrected,\n        "raw_text": text,\n    }'
    if old_ret in c18_text:
        c18_text = c18_text.replace(old_ret, new_ret)
    else:
        print(f"Warning: old_ret not found in c18 of {path}")

    nb['cells'][18]['source'] = [line + '\n' for line in c18_text.split('\n')[:-1]] + ([c18_text.split('\n')[-1]] if not c18_text.endswith('\n') else [])

    # Cell 21: track_records initialization & ocr_result update
    c21_text = ''.join(nb['cells'][21]['source'])
    old_init = '"n_attempts": 0, "best_timestamp": None,\n                "class_name": "vehicle",'
    new_init = '"n_attempts": 0, "best_timestamp": None,\n                "class_name": "vehicle", "raw_text": None, "was_corrected": False,'
    if old_init in c21_text:
        c21_text = c21_text.replace(old_init, new_init)
    else:
        print(f"Warning: old_init not found in c21 of {path}")

    old_update = '            if ocr_result is not None and ocr_result["combined_conf"] > rec["best_conf"]:\n                rec["best_text"] = ocr_result["text"]\n                rec["best_conf"] = ocr_result["combined_conf"]\n                rec["best_timestamp"] = abs_timestamp.isoformat()\n                if ocr_result["was_corrected"]:\n                    ocr_texts_corrected += 1'
    new_update = '            if ocr_result is not None and ocr_result["combined_conf"] > rec["best_conf"]:\n                rec["best_text"] = ocr_result["text"]\n                rec["best_conf"] = ocr_result["combined_conf"]\n                rec["best_timestamp"] = abs_timestamp.isoformat()\n                rec["raw_text"] = ocr_result.get("raw_text", ocr_result["text"])\n                rec["was_corrected"] = ocr_result.get("was_corrected", False)\n                if ocr_result["was_corrected"]:\n                    ocr_texts_corrected += 1'
    if old_update in c21_text:
        c21_text = c21_text.replace(old_update, new_update)
    else:
        print(f"Warning: old_update not found in c21 of {path}")

    nb['cells'][21]['source'] = [line + '\n' for line in c21_text.split('\n')[:-1]] + ([c21_text.split('\n')[-1]] if not c21_text.endswith('\n') else [])

    # Cell 23: events.append
    c23_text = ''.join(nb['cells'][23]['source'])
    old_append = '    events.append({\n        "event_id": event_id,\n        "camera_id": rec["camera_id"],\n        "plate": cleaned,\n        "timestamp": rec["best_timestamp"],'
    new_append = '    events.append({\n        "event_id": event_id,\n        "camera_id": rec["camera_id"],\n        "plate": cleaned,\n        "raw_plate": rec.get("raw_text", cleaned),\n        "was_corrected": rec.get("was_corrected", False),\n        "timestamp": rec["best_timestamp"],'
    if old_append in c23_text:
        c23_text = c23_text.replace(old_append, new_append)
    else:
        print(f"Warning: old_append not found in c23 of {path}")

    nb['cells'][23]['source'] = [line + '\n' for line in c23_text.split('\n')[:-1]] + ([c23_text.split('\n')[-1]] if not c23_text.endswith('\n') else [])

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f"Successfully updated {path}")

if __name__ == '__main__':
    update_notebook('ml/detect.ipynb')
    update_notebook('kaggle_pipeline/detect.ipynb')
