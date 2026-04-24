#!/usr/bin/env python3
"""
解析系统架构设计师考试题目HTML文件
"""

import os
import re
import json
from pathlib import Path

def parse_html_file(filepath):
    """解析单个HTML文件，提取题目"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    questions = []

    # 分割每个试题
    # 使用试题编号作为分割点
    pattern = r'<div>试题(\d+)\[(\d+)\]</div>'
    matches = list(re.finditer(pattern, content))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        block = content[start:end]

        q_num = int(match.group(1))
        q_id = match.group(2)

        # 提取题目内容
        question = {
            'number': q_num,
            'id': q_id,
            'type': 'choice',  # 默认为选择题
            'content': '',
            'image': '',  # 图片URL
            'options': [],
            'answer': '',
            'analysis': '',
            'knowledge_point': '',
            'pass_rate': ''
        }

        # 提取题目文本（试题编号后的<p>标签）
        content_match = re.search(r'</div>\s*<p>(.*?)</p>', block, re.DOTALL)
        if content_match:
            question['content'] = clean_html(content_match.group(1))

        # 提取图片URL
        img_match = re.search(r'<img[^>]+src="([^"]+)"', block)
        if img_match:
            question['image'] = img_match.group(1)

        # 提取选项（可能有多个选项组）
        options_blocks = re.findall(r'<div>\s*(A\..*?<br>.*?(?:<br>|</div>))', block, re.DOTALL)

        # 更精确的选项提取
        all_options = []
        option_groups = []

        # 找到所有选项div块（在试题信息和答案之前）
        info_match = re.search(r'<div>试题信息:', block)
        if info_match:
            options_section = block[content_match.end() if content_match else 0:info_match.start()]
        else:
            options_section = block

        # 提取选项组
        option_divs = re.findall(r'<div>(.*?)</div>', options_section, re.DOTALL)

        for div_content in option_divs:
            # 检查是否是选项（包含A. B. C. D.）
            if re.search(r'[A-D]\.', div_content):
                options = []
                for line in re.split(r'<br>', div_content):
                    line = clean_html(line).strip()
                    if line and re.match(r'^[A-D]\.', line):
                        opt_letter = line[0]
                        opt_text = line[2:].strip() if len(line) > 2 else ''
                        options.append({'letter': opt_letter, 'text': opt_text})
                if options:
                    option_groups.append(options)

        question['options'] = option_groups

        # 提取试题信息（通过率、知识点）
        info_match = re.search(r'<div>试题信息:(.*?)</div>', block, re.DOTALL)
        if info_match:
            info_text = info_match.group(1)
            pass_rate_match = re.search(r'通过率：(\d+%)', info_text)
            if pass_rate_match:
                question['pass_rate'] = pass_rate_match.group(1)

            knowledge_match = re.search(r'所属知识点：([^;<]+)', info_text)
            if knowledge_match:
                question['knowledge_point'] = knowledge_match.group(1).strip()

        # 提取答案
        answer_match = re.search(r'<div>答案</div>(.*?)</div>', block, re.DOTALL)
        if answer_match:
            answer_text = clean_html(answer_match.group(1)).strip()
            question['answer'] = answer_text

        # 提取试题分析
        analysis_match = re.search(r'<div>试题分析\s*(.*?)</div>', block, re.DOTALL)
        if analysis_match:
            question['analysis'] = clean_html(analysis_match.group(1))

        # 判断题型
        if len(option_groups) > 1:
            question['type'] = 'multi_choice'  # 多空选择题
        elif len(option_groups) == 1:
            question['type'] = 'choice'
        else:
            # 可能是案例分析题
            question['type'] = 'essay'

        questions.append(question)

    return questions

def clean_html(text):
    """清理HTML标签和特殊字符"""
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 替换HTML实体
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&ldquo;', '"', text)
    text = re.sub(r'&rdquo;', '"', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_case_analysis_file(filepath):
    """解析案例分析题"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    questions = []

    # 分割每个试题
    pattern = r'<div>试题(\d+)\[(\d+)\]</div>'
    matches = list(re.finditer(pattern, content))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        block = content[start:end]

        q_num = int(match.group(1))
        q_id = match.group(2)

        question = {
            'number': q_num,
            'id': q_id,
            'type': 'case_analysis',
            'content': '',
            'images': [],  # 图片URL数组（支持多图片）
            'sub_questions': [],
            'answer': '',
            'analysis': ''
        }

        # 提取题目说明 - 案例分析题内容跨多个<p>标签
        content_parts = []
        p_matches = re.findall(r'<p>(.*?)</p>', block, re.DOTALL)
        for p_content in p_matches:
            # 提取图片URL
            img_matches = re.findall(r'<img[^>]+src="([^"]+)"', p_content)
            for img_url in img_matches:
                question['images'].append(img_url)
            cleaned = clean_html(p_content)
            if cleaned and not cleaned.startswith('试题'):
                content_parts.append(cleaned)
        question['content'] = '\n\n'.join(content_parts)

        # 提取答案（可能也有图片）
        answer_match = re.search(r'<div>答案</div>(.*?)(?:<div>试题分析|<br><br><div>试题)', block, re.DOTALL)
        if answer_match:
            answer_block = answer_match.group(1)
            # 提取答案中的图片
            answer_img_matches = re.findall(r'<img[^>]+src="([^"]+)"', answer_block)
            question['answer_images'] = answer_img_matches
            question['answer'] = clean_html(answer_block)

        # 提取试题分析
        analysis_match = re.search(r'<div>试题分析</div>(.*?)(?:<br><br><div>试题\d|$)', block, re.DOTALL)
        if analysis_match:
            question['analysis'] = clean_html(analysis_match.group(1))

        questions.append(question)

    return questions

def parse_essay_file(filepath):
    """解析论文题"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    questions = []

    pattern = r'<div>试题(\d+)\[(\d+)\]</div>'
    matches = list(re.finditer(pattern, content))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        block = content[start:end]

        q_num = int(match.group(1))
        q_id = match.group(2)

        question = {
            'number': q_num,
            'id': q_id,
            'type': 'essay',
            'content': '',
            'essay_sample': '',  # 范文内容
            'images': [],  # 范文中的图片
            'answer': '',
            'analysis': ''
        }

        # 提取题目内容 - 论文题内容可能跨多个<p>标签
        content_parts = []
        p_matches = re.findall(r'<p>(.*?)</p>', block, re.DOTALL)
        for p_content in p_matches:
            cleaned = clean_html(p_content)
            if cleaned and not cleaned.startswith('试题'):
                content_parts.append(cleaned)
        question['content'] = '\n\n'.join(content_parts)

        # 提取答案/范文（论文题通常没有标准答案）
        answer_match = re.search(r'<div>答案</div>(.*?)(?:<div>试题分析|<br><br>)', block, re.DOTALL)
        if answer_match:
            ans = clean_html(answer_match.group(1))
            question['answer'] = ans if ans else '本题为论文写作题，请参考范文。'

        # 提取范文（论文题的试题分析实际是范文内容）
        analysis_match = re.search(r'<div>试题分析</div>(.*?)(?:<br><br><div>试题\d|$)', block, re.DOTALL)
        if analysis_match:
            analysis_block = analysis_match.group(1)
            # 提取范文中的图片
            img_matches = re.findall(r'<img[^>]+src="([^"]+)"', analysis_block)
            question['images'] = img_matches
            # 提取范文文本，保留段落结构
            essay_parts = []
            p_matches = re.findall(r'<p>(.*?)</p>', analysis_block, re.DOTALL)
            for p_content in p_matches:
                cleaned = clean_html(p_content)
                if cleaned:
                    essay_parts.append(cleaned)
            question['essay_sample'] = '\n\n'.join(essay_parts)

        questions.append(question)

    return questions

def scan_directory(base_path):
    """扫描目录结构"""
    result = {
        'chapter_practice': {},
        'mock_exams': {}
    }

    # 章节练习
    chapter_path = os.path.join(base_path, '章节练习（架构25上）/2025上')
    if os.path.exists(chapter_path):
        for filename in os.listdir(chapter_path):
            if filename.endswith('(含答案).html'):
                filepath = os.path.join(chapter_path, filename)
                chapter_name = filename.replace('(含答案).html', '')
                questions = parse_html_file(filepath)
                result['chapter_practice'][chapter_name] = questions

    # 模拟题
    mock_base = os.path.join(base_path, '架构模拟题2025上')

    # 综合知识
    comprehensive_path = os.path.join(mock_base, '综合')
    if os.path.exists(comprehensive_path):
        result['mock_exams']['综合'] = {}
        for filename in os.listdir(comprehensive_path):
            if filename.endswith('(含答案).html'):
                filepath = os.path.join(comprehensive_path, filename)
                exam_name = filename.replace('(含答案).html', '')
                questions = parse_html_file(filepath)
                result['mock_exams']['综合'][exam_name] = questions

    # 案例分析
    case_path = os.path.join(mock_base, '案例分析')
    if os.path.exists(case_path):
        result['mock_exams']['案例分析'] = {}
        for filename in os.listdir(case_path):
            if filename.endswith('(含答案).html'):
                filepath = os.path.join(case_path, filename)
                exam_name = filename.replace('(含答案).html', '')
                questions = parse_case_analysis_file(filepath)
                result['mock_exams']['案例分析'][exam_name] = questions

    # 论文写作
    essay_path = os.path.join(mock_base, '论文')
    if os.path.exists(essay_path):
        result['mock_exams']['论文'] = {}
        for filename in os.listdir(essay_path):
            if filename.endswith('(含答案).html'):
                filepath = os.path.join(essay_path, filename)
                exam_name = filename.replace('(含答案).html', '')
                questions = parse_essay_file(filepath)
                result['mock_exams']['论文'][exam_name] = questions

    return result

if __name__ == '__main__':
    base_path = '/Users/bandly/Documents/视频课程/0.希塞2505/4. 练习题'

    print("开始解析题目...")
    data = scan_directory(base_path)

    # 保留已有的 essay_samples 数据
    output_path = '/Users/bandly/dev/ruankao/questions_data.json'
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            if 'essay_samples' in existing_data:
                data['essay_samples'] = existing_data['essay_samples']
                print(f"保留已有的论文范本数据: {len(data['essay_samples'])}个分类")

    # 统计题目数量
    total_chapter = sum(len(q) for q in data['chapter_practice'].values())
    total_mock = 0
    for category in data['mock_exams'].values():
        total_mock += sum(len(q) for q in category.values())

    print(f"章节练习题目总数: {total_chapter}")
    print(f"模拟题题目总数: {total_mock}")

    # 保存为JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"题目数据已保存到: {output_path}")