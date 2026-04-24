#!/usr/bin/env python3
"""
解析论文范本HTML文件，提取题目和范文内容
"""

import os
import re
import json
from pathlib import Path
from html.parser import HTMLParser

class EssayHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_remark = False
        self.in_p = False
        self.in_title = False
        self.remark_content = ""
        self.p_content = ""
        self.title = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'div':
            if attrs_dict.get('class') == 'remark':
                self.in_remark = True
        elif tag == 'p':
            self.in_p = True
        elif tag == 'a':
            if attrs_dict.get('class') == 'two':
                self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'div' and self.in_remark:
            self.in_remark = False
        elif tag == 'p':
            self.in_p = False
        elif tag == 'a':
            self.in_title = False

    def handle_data(self, data):
        if self.in_remark:
            self.remark_content += data
        if self.in_p:
            self.p_content += data
        if self.in_title:
            self.title = data.strip()

def parse_html_file(filepath):
    """解析单个HTML文件，提取论文内容"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = EssayHTMLParser()
    parser.feed(content)

    # 从文件名提取ID
    match = re.search(r'-(\d+)\.html', filepath)
    essay_id = match.group(1) if match else ""

    # 从文件名提取标题
    filename = os.path.basename(filepath)
    title_match = re.search(r'(.+)-(\d+)\.html', filename)
    file_title = title_match.group(1).replace('【范文】', '').strip() if title_match else ""

    # 解析remark内容，分离问题和摘要
    remark = parser.remark_content.strip()

    # 提取问题部分
    question_match = re.search(r'【问题】(.+?)【摘要】', remark, re.DOTALL)
    question = question_match.group(1).strip() if question_match else ""

    # 如果没有找到【问题】标记，尝试其他方式
    if not question:
        # 尝试匹配"请围绕"开头的题目
        question_match = re.search(r'(请围绕.+?论述[^\n]*)', remark, re.DOTALL)
        if question_match:
            question = question_match.group(1).strip()
        else:
            # 使用remark前半部分
            parts = remark.split('【摘要】')
            if len(parts) > 1:
                question = parts[0].replace('摘要:', '').strip()
            else:
                question = remark[:500]

    # 提取摘要部分
    abstract_match = re.search(r'【摘要】(.+)', remark, re.DOTALL)
    abstract = abstract_match.group(1).strip() if abstract_match else ""

    # 提取正文（范文内容）
    essay_content = parser.p_content.strip()

    # 确定分类
    parent_dir = os.path.basename(os.path.dirname(filepath))

    return {
        'id': essay_id,
        'title': file_title or parser.title,
        'category': parent_dir,
        'question': question,
        'abstract': abstract,
        'content': essay_content,
        'file': filename
    }

def main():
    essay_dir = "/Users/bandly/Documents/视频课程/0.希塞2505/3. 2025上半年 系统架构设计师考前冲刺班/架构论文"

    essays = []

    # 遍历所有HTML文件
    for root, dirs, files in os.walk(essay_dir):
        for f in files:
            if f.endswith('.html'):
                filepath = os.path.join(root, f)
                try:
                    essay_data = parse_html_file(filepath)
                    if essay_data['content']:  # 只保留有内容的
                        essays.append(essay_data)
                        print(f"解析成功: {essay_data['title']} ({essay_data['id']})")
                except Exception as e:
                    print(f"解析失败: {filepath}, 错误: {e}")

    print(f"\n共解析 {len(essays)} 篇论文范本")

    # 加载现有题目数据
    json_path = "/Users/bandly/dev/ruankao/questions_data.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 添加论文范本数据
    # 按分类组织
    essay_samples = {}
    for essay in essays:
        category = essay['category']
        if category not in essay_samples:
            essay_samples[category] = []
        essay_samples[category].append({
            'id': essay['id'],
            'title': essay['title'],
            'question': essay['question'],
            'abstract': essay['abstract'],
            'content': essay['content']
        })

    # 添加到数据中
    data['essay_samples'] = essay_samples

    # 保存
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到 {json_path}")

    # 输出分类统计
    print("\n分类统计:")
    for cat, samples in sorted(essay_samples.items()):
        print(f"  {cat}: {len(samples)}篇")

if __name__ == '__main__':
    main()