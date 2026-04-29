const express = require('express');
const fs = require('fs');
const path = require('path');
const { Redis } = require('@upstash/redis');
const { reviewEssay } = require('./essay_reviewer');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '10mb' })); // 增加限制以支持论文内容

// 本地开发用文件存储，Vercel 用 Upstash Redis
const isLocal = !process.env.UPSTASH_URL;

let redis = null;
if (!isLocal) {
    redis = new Redis({
        url: process.env.UPSTASH_URL,
        token: process.env.UPSTASH_TOKEN
    });
}

const DATA_DIR = path.join(__dirname, 'data');
const STATS_FILE = path.join(DATA_DIR, 'stats.json');

// 默认用户名
const DEFAULT_USER = 'bandly';

if (isLocal && !fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}

if (isLocal && !fs.existsSync(STATS_FILE)) {
    fs.writeFileSync(STATS_FILE, JSON.stringify({ users: {} }, null, 2));
}

app.use(express.static(__dirname));

// 获取统计数据
app.get('/api/stats', async (req, res) => {
    try {
        const user = req.query.user || DEFAULT_USER;
        let stats;
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            stats = JSON.parse(data);
        } else {
            stats = await redis.get('stats') || { users: {} };
        }

        // 返回指定用户的数据
        if (!stats.users) stats.users = {};
        const userStats = stats.users[user] || { overall: {}, questions: {} };
        res.json(userStats);
    } catch (err) {
        res.json({ overall: {}, questions: {} });
    }
});

// 保存统计数据
app.post('/api/stats', async (req, res) => {
    try {
        const stats = req.body;
        if (isLocal) {
            fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2));
        } else {
            await redis.set('stats', stats);
        }
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// 更新单个题目的答题记录
app.post('/api/stats/question/:id', async (req, res) => {
    try {
        const questionId = req.params.id;
        const record = req.body;
        const user = req.query.user || DEFAULT_USER;

        let stats;
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            stats = JSON.parse(data);
        } else {
            stats = await redis.get('stats') || { users: {} };
        }

        if (!stats.users) stats.users = {};
        if (!stats.users[user]) stats.users[user] = { overall: {}, questions: {} };
        if (!stats.users[user].questions) stats.users[user].questions = {};

        stats.users[user].questions[questionId] = {
            ...stats.users[user].questions[questionId],
            ...record,
            lastUpdate: new Date().toISOString()
        };

        updateOverallStats(stats.users[user]);

        if (isLocal) {
            fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2));
        } else {
            await redis.set('stats', stats);
        }

        res.json({ success: true, stats: stats.users[user] });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// 更新总体统计
function updateOverallStats(stats) {
    if (!stats.questions) return;

    let totalAttempts = 0;
    let totalCorrect = 0;
    let totalWrong = 0;

    for (const q of Object.values(stats.questions)) {
        totalAttempts += q.attempts || 0;
        totalCorrect += q.correctCount || 0;
        totalWrong += q.wrongCount || 0;
    }

    stats.overall = {
        totalAttempts,
        totalCorrect,
        totalWrong,
        accuracy: totalAttempts > 0 ? Math.round((totalCorrect / totalAttempts) * 100) : 0,
        lastUpdate: new Date().toISOString()
    };
}

// 获取题目答题记录
app.get('/api/stats/question/:id', async (req, res) => {
    try {
        const questionId = req.params.id;
        const user = req.query.user || DEFAULT_USER;
        let stats;
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            stats = JSON.parse(data);
        } else {
            stats = await redis.get('stats') || { users: {} };
        }
        res.json(stats.users?.[user]?.questions?.[questionId] || {});
    } catch (err) {
        res.json({});
    }
});

// 论文评审记录文件
const ESSAY_RECORDS_FILE = path.join(DATA_DIR, 'essay_records.json');

if (isLocal && !fs.existsSync(ESSAY_RECORDS_FILE)) {
    fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify({ records: [] }, null, 2));
}

// 获取论文题目列表
app.get('/api/essay/questions', async (req, res) => {
    try {
        const questionsData = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions_data.json'), 'utf8'));
        const essayMock = questionsData.mock_exams?.['论文'] || {};

        const questions = [];
        for (const examName of Object.keys(essayMock)) {
            for (const q of essayMock[examName]) {
                // 提取题目关键词作为标题
                const titleMatch = q.content.match(/请围绕["""](.+?)["""]论题/) ||
                                   q.content.match(/论(.+?)\s*应用/) ||
                                   q.content.match(/论(.+?)及其应用/);
                const title = titleMatch ? titleMatch[1] : `论文题 ${q.id}`;

                questions.push({
                    id: q.id,
                    title: title.trim(),
                    content: q.content,
                    examName: examName.replace('2025年上半年系统架构设计师考试模拟试卷（论文写作，', '').replace('）', '')
                });
            }
        }

        res.json({ success: true, questions });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// 提交论文评审
app.post('/api/essay/review', async (req, res) => {
    try {
        const { questionId, abstract, content } = req.body;

        if (!abstract || !content) {
            return res.status(400).json({ success: false, error: '摘要和正文不能为空' });
        }

        // 获取题目信息
        const questionsData = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions_data.json'), 'utf8'));
        const essayMock = questionsData.mock_exams?.['论文'] || {};

        let question = null;
        for (const examName of Object.keys(essayMock)) {
            for (const q of essayMock[examName]) {
                if (q.id === questionId) {
                    question = q;
                    break;
                }
            }
            if (question) break;
        }

        if (!question) {
            return res.status(400).json({ success: false, error: '题目不存在' });
        }

        // 调用评审服务
        const review = await reviewEssay(question, abstract, content);

        if (!review.success) {
            return res.status(500).json({ success: false, error: review.error });
        }

        // 保存评审记录
        const recordId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
        const record = {
            id: recordId,
            questionId,
            questionTitle: question.content.match(/请围绕["""](.+?)["""]论题/)?.[1] ||
                           question.content.match(/论(.+?)\s*应用/)?.[1] ||
                           `论文题 ${questionId}`,
            abstract,
            content,
            review: review.result,
            createdAt: new Date().toISOString()
        };

        let records;
        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            records = JSON.parse(data);
        } else {
            records = await redis.get('essay_records') || { records: [] };
        }

        records.records.unshift(record); // 新记录放在最前面

        // 限制保存数量（最多100条）
        if (records.records.length > 100) {
            records.records = records.records.slice(0, 100);
        }

        if (isLocal) {
            fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify(records, null, 2));
        } else {
            await redis.set('essay_records', records);
        }

        res.json({ success: true, record, usage: review.usage });

    } catch (err) {
        console.error('Essay review error:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// 获取评审历史记录
app.get('/api/essay/records', async (req, res) => {
    try {
        let records;
        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            records = JSON.parse(data);
        } else {
            records = await redis.get('essay_records') || { records: [] };
        }
        res.json({ success: true, records: records.records });
    } catch (err) {
        res.json({ success: true, records: [] });
    }
});

// 删除评审记录
app.delete('/api/essay/records/:id', async (req, res) => {
    try {
        const recordId = req.params.id;

        let records;
        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            records = JSON.parse(data);
        } else {
            records = await redis.get('essay_records') || { records: [] };
        }

        records.records = records.records.filter(r => r.id !== recordId);

        if (isLocal) {
            fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify(records, null, 2));
        } else {
            await redis.set('essay_records', records);
        }

        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`刷题系统服务器运行在 http://localhost:${PORT}`);
});

module.exports = app;