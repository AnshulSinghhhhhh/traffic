import json

with open('ml/detect.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, c in enumerate(nb['cells']):
    src = c.get('source', '')
    if isinstance(src, str) and 'VIDEO_PATH =' in src:
        src = src.replace('WORK_DIR = "/content/idahr_v2"', 'WORK_DIR = "/kaggle/working"')
        src = src.replace('VIDEO_PATH = "/content/drive/MyDrive/NEW_START/input.mp4"', 'VIDEO_PATH = "/kaggle/input/idahr-video-and-weights/source.mp4"')
        src = src.replace('PLATE_WEIGHTS_PATH = "/content/drive/MyDrive/idahr_plate_detector.pt"', 'PLATE_WEIGHTS_PATH = "/kaggle/input/idahr-video-and-weights/idahr_plate_detector.pt"')
        c['source'] = src
        print(f"Updated config paths in cell {i}")

with open('kaggle_pipeline/detect.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Saved kaggle_pipeline/detect.ipynb successfully!")
