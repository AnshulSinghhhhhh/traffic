import json
import re

with open('kaggle_pipeline/kaggle_output/idahr-anpr-pipeline.log', 'r', encoding='utf-8') as f:
    text = f.read()

# Lines are json chunks like: [{"stream_name":"stdout","time":9.437961439,"data":"..."}
# Find all times
times = re.findall(r'"time":([0-9.]+)', text)
if times:
    t_start = float(times[0])
    t_end = float(times[-1])
    print(f"Log start time: {t_start:.1f}s, end time: {t_end:.1f}s, total span: {t_end - t_start:.1f}s")

# Find when cell 9 finished / cell 10 started (video processing)
m_cell9 = re.search(r'Helper functions ready', text)
if m_cell9:
    idx = text.rfind('"time":', 0, m_cell9.start())
    m_time = re.search(r'"time":([0-9.]+)', text[idx:idx+30])
    if m_time:
        t_vid_start = float(m_time.group(1))
        print(f"Video loop start time: {t_vid_start:.1f}s")

m_cell10_end = re.search(r'Processed 300 sampled frames', text)
if m_cell10_end:
    idx = text.rfind('"time":', 0, m_cell10_end.start())
    m_time = re.search(r'"time":([0-9.]+)', text[idx:idx+30])
    if m_time:
        t_vid_end = float(m_time.group(1))
        print(f"Video loop end time: {t_vid_end:.1f}s")
        vid_runtime = t_vid_end - t_vid_start
        fps = 300.0 / vid_runtime
        print(f"Video processing wall-clock time: {vid_runtime:.2f}s ({fps:.2f} frames/sec)")
