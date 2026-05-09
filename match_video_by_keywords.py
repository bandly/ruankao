#!/usr/bin/env python3
"""
基于手动标注关键词的视频匹配脚本
使用精确的专业术语关键词进行匹配
"""

import json
import os
import re

QUESTIONS_FILE = '/Users/bandly/dev/ruankao/questions_data.json'
KEYWORDS_FILE = '/Users/bandly/dev/ruankao/video_keywords_manual.json'
TRANSCRIPTS_DIR = '/Users/bandly/dev/ruankao/data/transcripts'

def load_keywords_index():
    """加载手动标注的关键词索引"""
    with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_video_path(video_name):
    """根据视频名称查找完整路径"""
    for filename in os.listdir(TRANSCRIPTS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(TRANSCRIPTS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('video_name') == video_name or filename.replace('.json', '') == video_name:
                    return data.get('video_path', ''), data.get('chapter', '')
    return '', ''

def match_by_keywords(knowledge_point, keywords_index):
    """基于手动关键词匹配"""
    if not knowledge_point:
        return []

    # 解析知识点
    kp_parts = knowledge_point.split('>')
    kp_text = ' '.join(kp_parts).replace('；', '').strip()

    # 提取知识点中的关键词
    kp_keywords = []
    for part in kp_parts:
        part = part.strip()
        # 添加完整知识点
        kp_keywords.append(part.lower())
        # 添加子关键词（连续中文、英文缩写）
        chinese_words = re.findall(r'[一-龥]+', part)
        english_words = re.findall(r'[A-Z]{2,}|[A-Za-z]+', part)
        kp_keywords.extend([w.lower() for w in chinese_words if len(w) >= 2])
        kp_keywords.extend([w.lower() for w in english_words if len(w) >= 2])

    # 匹配视频
    matched = []
    for video in keywords_index:
        video_name = video['video_name']
        video_keywords = [k.lower() for k in video.get('keywords', [])]

        # 计算匹配分数
        score = 0
        matched_kws = []

        for kp_kw in kp_keywords:
            for vk in video_keywords:
                # 精确匹配或包含匹配
                if kp_kw == vk:
                    score += 20
                    matched_kws.append(vk)
                elif kp_kw in vk or vk in kp_kw:
                    score += 10
                    matched_kws.append(vk)

        if score > 0:
            video_path, chapter = get_video_path(video_name)
            matched.append({
                'video_name': video_name,
                'video_path': video_path,
                'chapter': chapter,
                'score': score,
                'matched_keywords': matched_kws
            })

    # 按分数排序
    matched.sort(key=lambda x: x['score'], reverse=True)
    return matched[:5]

def compare_matching():
    """对比新旧匹配效果"""
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    keywords_index = load_keywords_index()

    print("=" * 70)
    print("新旧匹配对比")
    print("=" * 70)

    # 选取典型知识点进行对比
    test_kps = [
        '系统工程与信息系统基础>商业智能',
        '系统工程与信息系统基础>电子政务类型',
        '系统工程与信息系统基础>企业应用集成',
        '系统工程与信息系统基础>电子商务',
        '数据库系统>规范化理论',
        '软件工程>软件开发方法',
        '软件工程>软件过程模型',
        '软件架构设计>设计模式',
    ]

    for kp in test_kps:
        print(f"\n知识点: {kp}")

        # 新匹配结果
        new_matched = match_by_keywords(kp, keywords_index)

        print("  【新匹配结果】:")
        for m in new_matched[:3]:
            print(f"    ✓ {m['video_name']} (匹配: {m['matched_keywords'][:3]})")

        # 查找旧匹配结果
        for chapter, questions in questions_data.get('chapter_practice', {}).items():
            for q in questions:
                q_kp = q.get('knowledge_point', '')
                if kp.split('>')[0] in q_kp or kp.split('>')[1] in q_kp:
                    old_links = q.get('video_links', [])
                    if old_links:
                        print("  【旧匹配结果】:")
                        for v in old_links[:2]:
                            print(f"    • {v.get('title', '')}")
                        break

def update_questions():
    """更新题目的视频链接"""
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)

    keywords_index = load_keywords_index()
    updated_count = 0

    for chapter, questions in questions_data.get('chapter_practice', {}).items():
        for q in questions:
            kp = q.get('knowledge_point', '')
            matched = match_by_keywords(kp, keywords_index)

            if matched:
                video_links = []
                for m in matched[:3]:
                    video_links.append({
                        'title': m['video_name'],
                        'path': m['video_path'],
                        'matched_keywords': m['matched_keywords'],
                        'match_type': 'content_based'
                    })

                # 保存新的匹配结果（不覆盖旧的）
                q['video_links_new'] = video_links
                updated_count += 1

    # 保存更新
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions_data, f, ensure_ascii=False, indent=2)

    return updated_count

def main():
    print("基于内容关键词的视频匹配")
    print("=" * 70)

    # 先对比效果
    compare_matching()

    # 更新题目
    print("\n" + "=" * 70)
    updated = update_questions()
    print(f"已更新 {updated} 题目的新视频链接")

if __name__ == '__main__':
    main()