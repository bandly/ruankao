#!/usr/bin/env python3
"""
批量生成视频摘要索引
从转写文件生成摘要和关键词，保存到索引文件
"""

import os
import json
import re

TRANSCRIPTS_DIR = '/Users/bandly/dev/ruankao/data/transcripts'
INDEX_FILE = '/Users/bandly/dev/ruankao/video_content_index.json'

def extract_keywords_from_transcript(transcript):
    """从转写文本提取关键词"""
    # 移除标点符号
    text = transcript.replace('\n', ' ')

    # 提取中文词汇（2-4字）
    chinese_words = re.findall(r'[一-龥]{2,4}', text)

    # 提取英文缩写和术语
    english_terms = re.findall(r'[A-Z]{2,}|[A-Za-z]+', text)

    # 计算词频
    word_freq = {}
    for w in chinese_words:
        word_freq[w] = word_freq.get(w, 0) + 1
    for w in english_terms:
        if len(w) >= 2:
            word_freq[w] = word_freq.get(w, 0) + 1

    # 排序取高频词
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [w[0] for w in sorted_words[:15] if w[1] >= 2]

    return keywords

def generate_summary_from_transcript(transcript, max_length=150):
    """从转写文本生成简单摘要"""
    # 取前几句作为摘要
    sentences = re.split(r'[。！？]', transcript)
    summary = ''
    for s in sentences[:3]:
        if s.strip():
            summary += s.strip() + '。'

    # 截断到最大长度
    if len(summary) > max_length:
        summary = summary[:max_length] + '...'

    return summary

def build_index():
    """构建视频内容索引"""
    index = []

    # 扫描所有转写文件
    for filename in os.listdir(TRANSCRIPTS_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        transcript = data.get('transcript', '')
        if not transcript:
            continue

        # 提取关键词和生成摘要
        keywords = extract_keywords_from_transcript(transcript)
        summary = generate_summary_from_transcript(transcript)

        entry = {
            'video_path': data.get('video_path', ''),
            'video_name': data.get('video_name', filename.replace('.json', '')),
            'chapter': data.get('chapter', ''),
            'summary': summary,
            'keywords': keywords[:10],
        }

        index.append(entry)

    # 保存索引
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return len(index)

def main():
    print("构建视频内容索引...")
    count = build_index()
    print(f"已完成 {count} 个视频的索引")

    # 显示部分结果
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        index = json.load(f)

    print("\n索引示例:")
    for entry in index[:5]:
        print(f"  {entry['video_name']}: {entry['keywords'][:5]}")

if __name__ == '__main__':
    main()