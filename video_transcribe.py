#!/usr/bin/env python3
"""
视频语音识别脚本
使用 OpenAI Whisper 从视频提取语音并转换为文字

使用方法：
1. 安装依赖: pip install openai-whisper
2. 运行脚本: python video_transcribe.py
3. 输出文件保存在 data/transcripts/ 目录

测试视频（数据库章节）：
- 规范化理论
- 并发控制
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# 配置
VIDEO_BASE = '/Users/bandly/Documents/视频课程/0.希塞2505/1.【新版】系统架构设计师精讲班视频教程'
OUTPUT_DIR = '/Users/bandly/dev/ruankao/data/transcripts'

# 测试视频列表（数据库章节）
TEST_VIDEOS = [
    # 规范化理论相关 - 测试一个
    '11. 数据库系统/11.8. 规范化理论/11.8.1. 非规范化存在的问题.mp4',
]

def extract_audio(video_path, audio_path):
    """从视频提取音频"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn',  # 不包含视频
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        '-ar', '16000',  # 16kHz 采样率
        '-ac', '1',  # 单声道
        '-y',  # 覆盖已存在文件
        audio_path
    ]

    print(f"  提取音频: {os.path.basename(video_path)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  错误: {result.stderr[:200]}")
        return False
    return True

def transcribe_audio(audio_path, model_size='large-v3'):
    """使用 Whisper 进行语音识别"""
    try:
        import whisper
    except ImportError:
        print("请先安装 Whisper: pip install openai-whisper")
        sys.exit(1)

    print(f"  加载模型: {model_size}")
    model = whisper.load_model(model_size)

    print(f"  开始识别...")
    result = model.transcribe(audio_path, language='zh')

    return result['text'], result.get('segments', [])

def process_video(video_rel_path, model_size='large-v3'):
    """处理单个视频"""
    video_path = os.path.join(VIDEO_BASE, video_rel_path)

    if not os.path.exists(video_path):
        print(f"视频不存在: {video_path}")
        return None

    # 如果是目录，获取目录下的视频文件
    if os.path.isdir(video_path):
        videos_in_dir = []
        for f in sorted(os.listdir(video_path)):
            if f.endswith('.mp4') and not f.startswith('.'):
                videos_in_dir.append(os.path.join(video_path, f))

        results = []
        for v in videos_in_dir[:3]:  # 最多处理3个子视频
            r = process_single_video(v, model_size)
            if r:
                results.append(r)
        return results

    # 如果是文件，直接处理
    return process_single_video(video_path, model_size)

def process_single_video(video_path, model_size='large-v3'):
    """处理单个视频文件"""
    video_name = os.path.basename(video_path).replace('.mp4', '')

    print(f"\n处理视频: {video_name}")

    # 创建临时音频文件
    audio_path = os.path.join(OUTPUT_DIR, f'{video_name}.wav')

    # 提取音频
    if not extract_audio(video_path, audio_path):
        return None

    # 语音识别
    try:
        text, segments = transcribe_audio(audio_path, model_size)
    except Exception as e:
        print(f"  识别错误: {e}")
        return None

    # 保存结果
    output_file = os.path.join(OUTPUT_DIR, f'{video_name}.json')

    result = {
        'video_path': video_path,
        'video_name': video_name,
        'transcript': text,
        'segments': [
            {'start': s['start'], 'end': s['end'], 'text': s['text']}
            for s in segments
        ]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 删除临时音频文件
    os.remove(audio_path)

    print(f"  完成! 输出: {output_file}")
    print(f"  文字长度: {len(text)} 字符")

    return result

def main():
    print("=" * 50)
    print("视频语音识别脚本")
    print("=" * 50)

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 检查 Whisper 是否安装
    try:
        import whisper
        print("Whisper 已安装")
    except ImportError:
        print("\n请先安装 Whisper:")
        print("  pip install openai-whisper")
        print("\n建议使用 large-v3 模型（中文效果最好）")
        print("首次运行会自动下载模型（约 3GB）")
        sys.exit(1)

    # 模型大小选择
    # large-v3: 中文效果最好，但模型约 3GB，首次运行需下载
    # medium: 平衡速度和效果，模型约 1GB
    model_size = 'medium'  # 测试时使用 medium，正式处理建议 large-v3
    print(f"使用模型: {model_size}")

    # 处理测试视频
    all_results = []

    for video_rel_path in TEST_VIDEOS:
        results = process_video(video_rel_path, model_size)
        if results:
            if isinstance(results, list):
                all_results.extend(results)
            else:
                all_results.append(results)

    # 总结
    print("\n" + "=" * 50)
    print(f"处理完成! 共 {len(all_results)} 个视频")
    print("=" * 50)

    # 显示转写结果摘要
    for r in all_results:
        print(f"\n{r['video_name']}:")
        # 显示前200字符
        preview = r['transcript'][:200] if r['transcript'] else '(无内容)'
        print(f"  {preview}...")

    print("\n转写文件保存在:", OUTPUT_DIR)
    print("请将转写内容发给 Claude Code 进行摘要分析")

if __name__ == '__main__':
    main()