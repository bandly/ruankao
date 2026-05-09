#!/usr/bin/env python3
"""
基于视频内容索引的题目匹配脚本
使用语音识别提取的视频内容摘要和关键词进行精准匹配
"""

import json
import os
import re

QUESTIONS_FILE = '/Users/bandly/dev/ruankao/questions_data.json'
VIDEO_INDEX_FILE = '/Users/bandly/dev/ruankao/video_content_index.json'

def load_video_index():
    """加载视频内容索引"""
    if os.path.exists(VIDEO_INDEX_FILE):
        with open(VIDEO_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def match_by_keywords(knowledge_point, video_index):
    """基于关键词匹配视频"""
    if not knowledge_point or not video_index:
        return []

    # 解析知识点
    kp_parts = knowledge_point.split('>')
    kp_keywords = []
    for part in kp_parts:
        part = part.strip().replace('；', '').replace(',', '')
        # 添加完整知识点
        kp_keywords.append(part.lower())
        # 添加子关键词
        words = re.findall(r'[A-Za-z]+|[一-龥]+', part)
        for w in words:
            if len(w) >= 2:
                kp_keywords.append(w.lower())

    # 匹配视频
    matched = []
    for video in video_index:
        video_keywords = [k.lower() for k in video.get('keywords', [])]
        topics = [t.lower() for t in video.get('topics', [])]

        # 计算匹配分数
        score = 0
        matched_kws = []

        for kw in kp_keywords:
            for vk in video_keywords:
                if kw in vk or vk in kw:
                    score += 10
                    matched_kws.append(vk)
            for t in topics:
                if kw in t or t in kw:
                    score += 5
                    matched_kws.append(t)

        if score > 0:
            matched.append({
                'video': video,
                'score': score,
                'matched_keywords': matched_kws
            })

    # 按分数排序
    matched.sort(key=lambda x: x['score'], reverse=True)
    return matched[:5]

def update_video_links(questions_data, video_index):
    """更新题目的视频链接"""
    updated_count = 0

    # 处理章节练习
    for chapter, questions in questions_data.get('chapter_practice', {}).items():
        for q in questions:
            kp = q.get('knowledge_point', '')
            matched = match_by_keywords(kp, video_index)

            if matched:
                # 构建新的视频链接
                video_links = []
                for m in matched[:3]:
                    v = m['video']
                    video_links.append({
                        'title': v.get('video_name', ''),
                        'path': v.get('video_path', ''),
                        'matched_keywords': m['matched_keywords'],
                        'match_score': m['score']
                    })

                # 更新题目的视频链接
                q['video_links_content'] = video_links
                updated_count += 1

    return updated_count

def main():
    print("基于视频内容的题目匹配")

    # 加载视频索引
    video_index = load_video_index()
    print(f"已加载 {len(video_index)} 个视频内容索引")

    if not video_index:
        print("请先运行 video_transcribe.py 生成视频内容索引")
        return

    # 加载题目数据
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    # 更新匹配
    updated = update_video_links(questions_data, video_index)
    print(f"已更新 {updated} 题目的视频链接")

    # 显示匹配示例
    print("\n=== 匹配示例 ===")
    for chapter, questions in questions_data.get('chapter_practice', {}).items():
        for q in questions:
            if q.get('video_links_content'):
                kp = q.get('knowledge_point', '')
                print(f"\n知识点: {kp}")
                for vl in q['video_links_content']:
                    print(f"  → {vl['title']} (匹配关键词: {vl['matched_keywords']})")
                break

if __name__ == '__main__':
    main()