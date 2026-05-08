const OpenAI = require('openai');

// 初始化 OpenAI SDK（兼容多家平台）
const openai = new OpenAI({
    apiKey: process.env.LLM_API_KEY || process.env.DEEPSEEK_API_KEY || '',
    baseURL: process.env.LLM_BASE_URL || 'https://api.deepseek.com/v1'
});

const MODEL = process.env.LLM_MODEL || 'deepseek-chat';

// 评审 Prompt 设计
const REVIEW_PROMPT = `你是一位资深的软考（系统架构设计师）论文评审专家，拥有多年阅卷经验。请根据以下评分标准对用户提交的论文进行评审。

## 评分标准（总分100分）

1. **项目背景真实性**（15分）
   - 项目描述是否具体、可信（项目名称、规模、时间、团队等）
   - 是否有明确的项目角色和工作内容
   - 项目技术背景是否合理

2. **问题分析与解决**（25分）
   - 是否清晰阐述了技术问题和挑战
   - 解决方案是否合理、有针对性
   - 技术选型是否有依据

3. **结构完整性**（20分）
   - 摘要是否包含：项目概述、技术要点、结论三部分
   - 正文是否按题目要求的三个方面论述
   - 各部分比例是否合理

4. **语言表达**（15分）
   - 专业术语使用是否准确
   - 逻辑是否流畅、条理清晰
   - 是否有明显的语法或表达错误

5. **论点深度**（15分）
   - 技术论点是否有深度、有见解
   - 是否结合了具体实践案例
   - 是否有反思和总结

6. **字数达标**（10分）
   - 摘要应在300字左右（220-380字为合格范围）
   - 正文应在2000-2500字之间

## 评审要求

请严格按照以上标准进行评审，输出JSON格式的评审结果，包含以下字段：

{
  "scores": {
    "项目背景真实性": <分数>,
    "问题分析与解决": <分数>,
    "结构完整性": <分数>,
    "语言表达": <分数>,
    "论点深度": <分数>,
    "字数达标": <分数>
  },
  "totalScore": <总分>,
  "abstractWordCount": <摘要字数>,
  "contentWordCount": <正文字数>,
  "issues": [<发现的问题列表，每条一句>],
  "suggestions": [<改进建议列表，每条一句>],
  "strengths": [<优点列表，可选>],
  "summary": "<整体评价，一句话总结>"
}

请只输出JSON，不要输出其他内容。`;

/**
 * 评审论文
 * @param {Object} question - 论文题目信息
 * @param {string} abstract - 用户提交的摘要
 * @param {string} content - 用户提交的正文
 * @returns {Object} 评审结果
 */
async function reviewEssay(question, abstract, content) {
    const userPrompt = `## 论文题目

${question.content}

## 用户提交的摘要

${abstract}

## 用户提交的正文

${content}

请根据评分标准对这篇论文进行评审，输出JSON格式的评审结果。`;

    try {
        const response = await openai.chat.completions.create({
            model: MODEL,
            messages: [
                { role: 'system', content: REVIEW_PROMPT },
                { role: 'user', content: userPrompt }
            ],
            temperature: 0.3, // 降低随机性，提高评审一致性
            max_tokens: 2000
        });

        const resultText = response.choices[0].message.content;

        // 解析 JSON 结果
        let reviewResult;
        try {
            // 提取 JSON（处理可能的 markdown 包装）
            const jsonMatch = resultText.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                reviewResult = JSON.parse(jsonMatch[0]);
            } else {
                reviewResult = JSON.parse(resultText);
            }
        } catch (parseError) {
            console.error('JSON parse error:', parseError);
            // 返回基础结果
            reviewResult = {
                scores: {},
                totalScore: 0,
                issues: ['评审结果解析失败'],
                suggestions: ['请检查论文格式后重新提交'],
                summary: resultText
            };
        }

        return {
            success: true,
            result: reviewResult,
            usage: response.usage
        };

    } catch (error) {
        console.error('Review API error:', error);
        return {
            success: false,
            error: error.message || '评审服务调用失败'
        };
    }
}

module.exports = {
    reviewEssay,
    MODEL
};