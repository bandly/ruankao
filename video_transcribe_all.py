#!/usr/bin/env python3
"""
批量处理所有视频 - 提取语音并转换为文字

扫描视频目录，批量提取语音并识别
"""

import os
import sys
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

# 配置
VIDEO_BASE = '/Users/bandly/Documents/视频课程/0.希塞2505/1.【新版】系统架构设计师精讲班视频教程'
OUTPUT_DIR = '/Users/bandly/dev/ruankao/data/transcripts'
INDEX_FILE = '/Users/bandly/dev/ruankao/video_content_index.json'

# 题目章节 -> 视频章节映射
CHAPTER_MAP = {
    '第1章 系统工程与信息系统基础': '2. 系统工程与信息系统基础',
    '第2章 软件工程': '3. 软件工程',
    '第3章 项目管理': '4. 项目管理',
    '第4章 软件架构设计': '5. 软件架构设计',
    '第5章 系统可靠性分析与设计': '6. 系统可靠性分析与设计',
    '第6章 信息安全技术基础知识': '7. 信息安全技术基础知识',
    '第7章 计算机系统基础': '8. 计算机系统基础',
    '第8章 嵌入式系统': '9. 嵌入式系统',
    '第9章 计算机网络': '10. 计算机网络',
    '第10章 数据库系统': '11. 数据库系统',
    '第11章 未来信息技术': '12. 未来信息综合技术',
    '第12章 知识产权与标准化': '13. 知识产权与标准化',
}

def scan_all_videos():
    """扫描所有章节视频"""
    all_videos = []

    for q_chapter, video_folder in CHAPTER_MAP.items():
        video_path = os.path.join(VIDEO_BASE, video_folder)
        if not os.path.exists(video_path):
            print(f"  目录不存在: {video_folder}")
            continue

        print(f"扫描: {video_folder}")

        # 递归扫描所有 mp4 文件
        for root, dirs, files in os.walk(video_path):
            for f in files:
                if f.endswith('.mp4') and not f.startswith('.'):
                    full_path = os.path.join(root, f)
                    # 解析视频标题
                    match = re.match(r'^(\d+\.){1,3}(.+?)\.mp4$', f)
                    if match:
                        title = match.group(2).strip()
                    else:
                        title = f.replace('.mp4', '')

                    all_videos.append({
                        'path': full_path,
                        'title': title,
                        'chapter': q_chapter,
                        'folder': video_folder,
                    })

    return all_videos

def extract_audio(video_path, audio_path):
    """从视频提取音频"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def transcribe_audio(audio_path, model):
    """使用 Whisper 进行语音识别"""
    result = model.transcribe(audio_path, language='zh')
    return result['text'], result.get('segments', [])

def process_video(video_info, model, progress_info):
    """处理单个视频"""
    video_path = video_info['path']
    title = video_info['title']

    # 检查是否已处理
    output_file = os.path.join(OUTPUT_DIR, f'{title}.json')
    if os.path.exists(output_file):
        print(f"  [跳过] {title} (已存在)")
        return None

    print(f"  [{progress_info['current']}/{progress_info['total']}] 处理: {title}")

    # 创建临时音频文件
    audio_path = os.path.join(OUTPUT_DIR, f'{title}.wav')

    # 提取音频
    if not extract_audio(video_path, audio_path):
        print(f"    音频提取失败")
        return None

    # 语音识别
    try:
        text, segments = transcribe_audio(audio_path, model)
    except Exception as e:
        print(f"    识别错误: {e}")
        return None

    # 保存结果
    result = {
        'video_path': video_path,
        'video_name': title,
        'chapter': video_info['chapter'],
        'transcript': text,
        'segments_count': len(segments),
        'processed_at': datetime.now().isoformat(),
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 删除临时音频
    os.remove(audio_path)

    print(f"    完成: {len(text)} 字符")
    return result

def main():
    print("=" * 60)
    print("批量处理所有视频")
    print("=" * 60)

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 检查 Whisper
    try:
        import whisper
        print("Whisper 已安装")
    except ImportError:
        print("请先安装: pip install openai-whisper")
        sys.exit(1)

    # 扫描所有视频
    print("\n扫描视频目录...")
    all_videos = scan_all_videos()
    print(f"共找到 {len(all_videos)} 个视频")

    # 加载模型 - 使用small模型，速度快3-4倍
    model_size = 'small'
    print(f"\n加载模型: {model_size} (首次加载约需 1-2 分钟)")
    model = whisper.load_model(model_size)
    print("模型加载完成 (small模型处理速度约10分钟/视频)")

    # 处理所有视频
    progress = {'total': len(all_videos), 'current': 0}
    results = []
    errors = []

    print("\n开始处理...")
    start_time = datetime.now()

    for video_info in all_videos:
        progress['current'] += 1
        try:
            result = process_video(video_info, model, progress)
            if result:
                results.append(result)
        except Exception as e:
            errors.append({'video': video_info['title'], 'error': str(e)})
            print(f"    错误: {e}")

    # 总结
    elapsed = datetime.now() - start_time
    print("\n" + "=" * 60)
    print(f"处理完成!")
    print(f"  成功: {len(results)} 个视频")
    print(f"  错误: {len(errors)} 个")
    print(f"  耗时: {elapsed}")
    print("=" * 60)

    # 显示已处理视频列表
    print("\n已处理视频:")
    for r in results[:20]:
        print(f"  {r['video_name']}: {len(r['transcript'])} 字符")

    if len(results) > 20:
        print(f"  ... 还有 {len(results) - 20} 个")

    # 保存处理统计
    stats = {
        'total_videos': len(all_videos),
        'processed': len(results),
        'errors': len(errors),
        'elapsed_seconds': elapsed.total_seconds(),
        'processed_at': datetime.now().isoformat(),
    }

    with open(os.path.join(OUTPUT_DIR, 'processing_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"\n转写文件保存在: {OUTPUT_DIR}")
    print("请将转写内容发给 Claude Code 进行摘要分析")

if __name__ == '__main__':
    main()