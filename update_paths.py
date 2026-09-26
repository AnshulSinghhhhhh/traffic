import json

with open('kaggle_pipeline/detect.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, c in enumerate(nb['cells']):
    src = c.get('source', '')
    if isinstance(src, str) and 'VIDEO_PATH =' in src:
        # replace with robust glob search
        snippet = """
import glob
video_matches = glob.glob('/kaggle/input/**/source.mp4', recursive=True) or glob.glob('/kaggle/input/**/*.mp4', recursive=True)
weights_matches = glob.glob('/kaggle/input/**/idahr_plate_detector.pt', recursive=True) or glob.glob('/kaggle/input/**/*.pt', recursive=True)
print("Found video matches:", video_matches)
print("Found weights matches:", weights_matches)
VIDEO_PATH = video_matches[0] if video_matches else "/kaggle/input/idahr-video-and-weights/source.mp4"
PLATE_WEIGHTS_PATH = weights_matches[0] if weights_matches else "/kaggle/input/idahr-video-and-weights/idahr_plate_detector.pt"
"""
        src = src.replace('VIDEO_PATH = "/kaggle/input/idahr-video-and-weights/source.mp4"', '')
        src = src.replace('PLATE_WEIGHTS_PATH = "/kaggle/input/idahr-video-and-weights/idahr_plate_detector.pt"', '')
        src += "\n" + snippet
        c['source'] = src
        print(f"Updated cell {i} with dynamic glob locator")

with open('kaggle_pipeline/detect.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Saved kaggle_pipeline/detect.ipynb!")
