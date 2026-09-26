import os
import shutil
import json

upload_dir = 'kaggle_dataset_upload'
os.makedirs(upload_dir, exist_ok=True)

meta = {
  "title": "idahr-video-and-weights",
  "id": "anshulsingh45/idahr-video-and-weights",
  "licenses": [
    {
      "name": "CC0-1.0"
    }
  ]
}

with open(os.path.join(upload_dir, 'dataset-metadata.json'), 'w') as f:
    json.dump(meta, f, indent=2)

# Copy or hardlink source.mp4 and idahr_plate_detector.pt
src_mp4 = 'source.mp4'
dst_mp4 = os.path.join(upload_dir, 'source.mp4')
if not os.path.exists(dst_mp4):
    try:
        os.link(src_mp4, dst_mp4)
        print("Hardlinked source.mp4")
    except Exception:
        shutil.copy(src_mp4, dst_mp4)
        print("Copied source.mp4")

src_pt = 'idahr_plate_detector.pt'
dst_pt = os.path.join(upload_dir, 'idahr_plate_detector.pt')
if not os.path.exists(dst_pt):
    try:
        os.link(src_pt, dst_pt)
        print("Hardlinked idahr_plate_detector.pt")
    except Exception:
        shutil.copy(src_pt, dst_pt)
        print("Copied idahr_plate_detector.pt")

print("Dataset upload directory prepared:")
print(os.listdir(upload_dir))
