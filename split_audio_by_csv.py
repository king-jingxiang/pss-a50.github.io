#!/usr/bin/env python3
import argparse
import subprocess
import shutil
import sys
from pathlib import Path
import csv

def check_tools():
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('缺少FFmpeg或FFprobe，请安装后重试')
        sys.exit(1)

def parse_timestamps(csv_path: Path):
    rows = []
    with open(str(csv_path), 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if len(row) < 2:
                continue
            try:
                s = float(row[0].strip())
                e = float(row[1].strip())
                rows.append((s, e))
            except Exception:
                continue
    return rows

def infer_audio_path(ts_path: Path):
    exts = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma', '.mp4', '.mkv', '.webm'}
    base = ts_path.stem
    if base.endswith('_segments'):
        base = base[:-10]
    candidates = []
    for p in ts_path.parent.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            if p.stem == base:
                return p
            candidates.append(p)
    if len(candidates) == 1:
        return candidates[0]
    return None

def export_segment(input_path: Path, start: float, end: float, out_path: Path):
    t = max(end - start, 0.01)
    cmd = ['ffmpeg', '-hide_banner', '-y', '-i', str(input_path), '-ss', str(start), '-t', str(t), '-c', 'copy', str(out_path)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f'导出失败: {out_path}')
        sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog='split-audio-by-csv', description='按CSV时间戳分割音频并导出片段')
    p.add_argument('timestamps', help='时间戳CSV文件路径')
    p.add_argument('-i', '--input', help='输入音频文件路径')
    p.add_argument('-o', '--output-dir', default='./outputs/audio_split', help='输出目录')
    p.add_argument('--min-seg', type=float, default=0.5, help='最小片段时长(秒)')
    p.add_argument('--start-index', type=int, default=1, help='起始序号')
    p.add_argument('--dry-run', action='store_true', help='仅打印计划，不实际导出')
    args = p.parse_args()

    ts_path = Path(args.timestamps)
    if not ts_path.exists():
        print(f'文件不存在: {ts_path}')
        sys.exit(1)

    segments_raw = parse_timestamps(ts_path)
    segments = [(s, e) for s, e in segments_raw if e > s and (e - s) >= args.min_seg]

    print(f'读取时间戳: {len(segments_raw)}')
    print(f'有效片段: {len(segments)}')

    if args.dry_run and not args.input:
        print('干运行，不执行导出')
        return

    input_path = Path(args.input) if args.input else infer_audio_path(ts_path)
    if input_path is None:
        print('未找到音频文件，请使用 --input 指定')
        sys.exit(1)
    if not input_path.exists():
        print(f'文件不存在: {input_path}')
        sys.exit(1)

    if not args.dry_run:
        check_tools()

    ext = input_path.suffix.lower()
    base = input_path.stem
    outdir = Path(args.output_dir) / base
    outdir.mkdir(parents=True, exist_ok=True)

    print(f'输出目录: {outdir}')

    idx = args.start_index
    for s, e in segments:
        name = f'{base}_{idx:03d}{ext}'
        outpath = outdir / name
        if args.dry_run:
            print(f'计划生成: {outpath.name} [{s:.3f} → {e:.3f}]')
        else:
            export_segment(input_path, s, e, outpath)
            print(f'生成: {outpath.name} [{s:.3f} → {e:.3f}]')
        idx += 1

if __name__ == '__main__':
    main()