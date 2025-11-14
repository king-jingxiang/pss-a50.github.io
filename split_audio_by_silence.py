#!/usr/bin/env python3
import argparse
import subprocess
import shutil
import sys
from pathlib import Path
import re

def check_tools():
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('缺少FFmpeg或FFprobe，请安装后重试')
        sys.exit(1)

def probe_duration(input_path: Path) -> float:
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(input_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        print('无法获取音频时长')
        sys.exit(1)
    return float(r.stdout.strip())

def detect_silences(input_path: Path, noise_db: float, min_silence: float):
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-i', str(input_path), '-af', f'silencedetect=noise={noise_db}dB:d={min_silence}', '-f', 'null', '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    text = r.stderr
    starts = [float(x) for x in re.findall(r'silence_start:\s*([0-9\.]+)', text)]
    ends = [float(x) for x in re.findall(r'silence_end:\s*([0-9\.]+)', text)]
    out = []
    i = j = 0
    while i < len(starts) and j < len(ends):
        if ends[j] >= starts[i]:
            out.append((starts[i], ends[j]))
            i += 1
            j += 1
        else:
            j += 1
    return out

def build_segments(silences, duration: float):
    segments = []
    cur = 0.0
    for s, e in silences:
        if s > cur:
            segments.append((cur, s))
        cur = max(cur, e)
    if duration > cur:
        segments.append((cur, duration))
    return [(round(a, 3), round(b, 3)) for a, b in segments if b - a > 0.01]

def write_timestamps(path: Path, segments):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), 'w', encoding='utf-8') as f:
        for s, e in segments:
            f.write(f"{s:.3f},{e:.3f}\n")

def export_segment(input_path: Path, start: float, end: float, out_path: Path):
    t = max(end - start, 0.01)
    cmd = ['ffmpeg', '-hide_banner', '-y', '-i', str(input_path), '-ss', str(start), '-t', str(t), '-c', 'copy', str(out_path)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f'导出失败: {out_path}')
        sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog='split-audio-by-silence', description='按最小停顿时长与阈值分割音频并导出CSV与片段')
    p.add_argument('input', help='输入音频文件路径')
    p.add_argument('-o', '--output-dir', default='./outputs/audio_split', help='输出目录')
    p.add_argument('--min-silence', type=float, default=0.8, help='最小停顿时长(秒)')
    p.add_argument('--threshold', type=float, default=-35.0, help='停顿阈值(dB)')
    p.add_argument('--min-seg', type=float, default=5, help='最小片段时长(秒)')
    p.add_argument('--start-index', type=int, default=1, help='起始序号')
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'文件不存在: {input_path}')
        sys.exit(1)

    check_tools()
    duration = probe_duration(input_path)
    silences = detect_silences(input_path, args.threshold, args.min_silence)
    segments_all = build_segments(silences, duration)
    segments = [(s, e) for s, e in segments_all if e - s >= args.min_seg]

    ext = input_path.suffix.lower()
    base = input_path.stem
    outdir = Path(args.output_dir) / base
    outdir.mkdir(parents=True, exist_ok=True)

    print(f'总时长: {duration:.3f} 秒')
    print(f'检测到停顿段: {len(silences)}')
    print(f'导出片段: {len(segments)}')

    ts_out_path = outdir / f'{base}_segments.csv'
    write_timestamps(ts_out_path, segments)
    print(f'写入时间戳: {ts_out_path}')

    idx = args.start_index
    for s, e in segments:
        name = f'{base}_{idx:03d}{ext}'
        outpath = outdir / name
        export_segment(input_path, s, e, outpath)
        print(f'生成: {outpath.name} [{s:.3f} → {e:.3f}]')
        idx += 1

if __name__ == '__main__':
    main()