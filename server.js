const express = require('express');
const fs = require('fs');
const path = require('path');
const Redis = require('ioredis');
const { reviewEssay } = require('./essay_reviewer');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '10mb' }));

// 本地开发用文件存储，Vercel 用 Redis
const redisUrl = process.env.ruankao_REDIS_URL || process.env.RUANKAO_REDIS_URL;
const isLocal = !redisUrl;

let redis = null;
if (!isLocal) {
    redis = new Redis(redisUrl, {
        maxRetriesPerRequest: 3,
        enableReadyCheck: false,
        enableOfflineQueue: true
    });
    redis.on('error', (err) => console.error('Redis error:', err.message));
}

const DATA_DIR = path.join(__dirname, 'data');
const STATS_FILE = path.join(DATA_DIR, 'stats.json');
const DEFAULT_USER = 'bandly';

if (isLocal && !fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}
if (isLocal && !fs.existsSync(STATS_FILE)) {
    fs.writeFileSync(STATS_FILE, JSON.stringify({ users: {} }, null, 2));
}

app.use(express.static(__dirname));

// Redis key helpers
const getUserKey = (user) => `stats:${user}`;
const getQuestionField = (qid) => `q:${qid}`;

// 视频目录静态服务
const VIDEO_BASE_PATH = '/Users/bandly/Documents/视频课程/0.希塞2505/1.【新版】系统架构设计师精讲班视频教程';
app.use('/videos', express.static(VIDEO_BASE_PATH));

// 视频搜索API
const VIDEO_KEYWORDS_FILE = path.join(__dirname, 'video_keywords_manual.json');
const TRANSCRIPTS_DIR = path.join(__dirname, 'data/transcripts');

app.get('/api/videos/search', (req, res) => {
    try {
        const keyword = req.query.q || '';
        if (!keyword || keyword.length < 1) {
            return res.json({ success: true, videos: [] });
        }

        // 加载视频关键词索引
        let keywordsIndex = [];
        if (fs.existsSync(VIDEO_KEYWORDS_FILE)) {
            keywordsIndex = JSON.parse(fs.readFileSync(VIDEO_KEYWORDS_FILE, 'utf8'));
        }

        // 加载转写文件
        let transcripts = [];
        if (fs.existsSync(TRANSCRIPTS_DIR)) {
            for (const filename of fs.readdirSync(TRANSCRIPTS_DIR)) {
                if (filename.endsWith('.json')) {
                    const filepath = path.join(TRANSCRIPTS_DIR, filename);
                    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
                    transcripts.push({
                        name: data.video_name || filename.replace('.json', ''),
                        path: data.video_path || '',
                        chapter: data.chapter || '',
                        transcript: data.transcript || ''
                    });
                }
            }
        }

        // 搜索
        const keywordLower = keyword.toLowerCase();
        const results = [];

        // 先从关键词索引搜索（精确匹配）
        for (const video of keywordsIndex) {
            const videoKeywords = (video.keywords || []).map(k => k.toLowerCase());
            const matchScore = videoKeywords.some(k => k.includes(keywordLower) || keywordLower.includes(k));
            if (matchScore) {
                // 查找完整路径
                const transcript = transcripts.find(t => t.name === video.video_name);
                results.push({
                    name: video.video_name,
                    path: transcript?.path || '',
                    chapter: transcript?.chapter || '',
                    keywords: video.keywords,
                    matchType: 'keyword',
                    score: 20
                });
            }
        }

        // 从视频名称和转写文本搜索
        for (const t of transcripts) {
            if (results.find(r => r.name === t.name)) continue; // 已在关键词结果中

            const nameMatch = t.name.toLowerCase().includes(keywordLower);
            const transcriptMatch = t.transcript && t.transcript.toLowerCase().includes(keywordLower);

            if (nameMatch || transcriptMatch) {
                results.push({
                    name: t.name,
                    path: t.path,
                    chapter: t.chapter,
                    keywords: [],
                    matchType: nameMatch ? 'name' : 'transcript',
                    score: nameMatch ? 15 : 10
                });
            }
        }

        // 按分数排序
        results.sort((a, b) => b.score - a.score);

        res.json({ success: true, videos: results.slice(0, 20), total: results.length });
    } catch (err) {
        console.error('Video search error:', err);
        res.json({ success: true, videos: [], total: 0 });
    }
});

// 保存视频关联到题目
app.post('/api/questions/video', (req, res) => {
    try {
        const { questionId, videoPath, videoName } = req.body;
        if (!questionId || !videoPath) {
            return res.status(400).json({ success: false, error: '缺少参数' });
        }

        // 加载题目数据
        const questionsFile = path.join(__dirname, 'questions_data.json');
        const questionsData = JSON.parse(fs.readFileSync(questionsFile, 'utf8'));

        // 找到题目并更新
        let found = false;
        for (const chapter of Object.keys(questionsData.chapter_practice || {})) {
            const questions = questionsData.chapter_practice[chapter];
            for (const q of questions) {
                if (q.id === questionId) {
                    // 添加或更新 user_video_links
                    if (!q.user_video_links) q.user_video_links = [];

                    // 检查是否已存在
                    const exists = q.user_video_links.find(v => v.path === videoPath);
                    if (!exists) {
                        q.user_video_links.unshift({
                            title: videoName,
                            path: videoPath,
                            addedAt: new Date().toISOString(),
                            addedBy: 'user'
                        });
                    }
                    found = true;
                    break;
                }
            }
            if (found) break;
        }

        // 也检查模拟题
        if (!found) {
            for (const examType of Object.keys(questionsData.mock_exams || {})) {
                for (const examName of Object.keys(questionsData.mock_exams[examType] || {})) {
                    const questions = questionsData.mock_exams[examType][examName];
                    for (const q of questions) {
                        if (q.id === questionId) {
                            if (!q.user_video_links) q.user_video_links = [];
                            const exists = q.user_video_links.find(v => v.path === videoPath);
                            if (!exists) {
                                q.user_video_links.unshift({
                                    title: videoName,
                                    path: videoPath,
                                    addedAt: new Date().toISOString(),
                                    addedBy: 'user'
                                });
                            }
                            found = true;
                            break;
                        }
                    }
                    if (found) break;
                }
                if (found) break;
            }
        }

        if (!found) {
            return res.status(404).json({ success: false, error: '题目不存在' });
        }

        // 保存
        fs.writeFileSync(questionsFile, JSON.stringify(questionsData, null, 2));

        res.json({ success: true, message: '视频已关联到题目' });
    } catch (err) {
        console.error('Save video error:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

app.get('/api/video/:path', (req, res) => {
    try {
        const videoPath = req.params.path;
        const relativePath = videoPath.replace(VIDEO_BASE_PATH, '');
        res.json({ success: true, url: `/videos${relativePath}`, path: videoPath });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// 获取统计数据 - 使用 Redis Hash
app.get('/api/stats', async (req, res) => {
    try {
        const user = req.query.user || DEFAULT_USER;
        const key = getUserKey(user);

        let questions = {};
        let overall = { totalAttempts: 0, totalCorrect: 0, totalWrong: 0, accuracy: 0 };

        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            const stats = JSON.parse(data);
            if (stats.users?.[user]) {
                questions = stats.users[user].questions || {};
                overall = stats.users[user].overall || overall;
            }
        } else {
            // 使用 HGETALL 获取用户所有数据
            const allData = await redis.hgetall(key);
            for (const [field, value] of Object.entries(allData)) {
                if (field === 'overall') {
                    overall = JSON.parse(value);
                } else if (field.startsWith('q:')) {
                    const qid = field.slice(2);
                    questions[qid] = JSON.parse(value);
                }
            }
        }

        // 确保 overall 统计是最新的
        updateOverallStats({ questions, overall });

        res.json({ overall, questions });
    } catch (err) {
        console.error('Stats error:', err);
        res.json({ overall: {}, questions: {} });
    }
});

// 更新单个题目的答题记录 - 使用 Redis Hash，只操作单个 field
app.post('/api/stats/question/:id', async (req, res) => {
    try {
        const questionId = req.params.id;
        const record = req.body;
        const user = req.query.user || DEFAULT_USER;
        const key = getUserKey(user);
        const field = getQuestionField(questionId);

        // 获取现有记录
        let existing = { attempts: 0, correctCount: 0, wrongCount: 0 };
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            const stats = JSON.parse(data);
            existing = stats.users?.[user]?.questions?.[questionId] || existing;
        } else {
            const data = await redis.hget(key, field);
            if (data) existing = JSON.parse(data);
        }

        // 更新记录
        const updated = {
            attempts: existing.attempts + 1,
            correctCount: existing.correctCount + (record.correctCount > existing.correctCount ? 1 : 0),
            wrongCount: existing.wrongCount + (record.wrongCount > existing.wrongCount ? 1 : 0),
            lastUpdate: new Date().toISOString()
        };

        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            const stats = JSON.parse(data);
            if (!stats.users) stats.users = {};
            if (!stats.users[user]) stats.users[user] = { overall: {}, questions: {} };
            stats.users[user].questions[questionId] = updated;

            updateOverallStats(stats.users[user]);
            stats.users[user].overall.lastUpdate = new Date().toISOString();

            fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2));
            res.json({ success: true, stats: stats.users[user] });
        } else {
            // 只更新单个题目 field，速度快
            await redis.hset(key, field, JSON.stringify(updated));

            // 异步更新 overall，并等待结果返回
            const overall = await updateOverallStatsAsync(user);

            // 返回完整的 stats（与本地模式格式一致）
            // 获取当前所有题目记录
            const allData = await redis.hgetall(key);
            const questions = {};
            for (const [f, v] of Object.entries(allData)) {
                if (f.startsWith('q:')) {
                    questions[f.slice(2)] = JSON.parse(v);
                }
            }

            res.json({ success: true, stats: { overall, questions } });
        }
    } catch (err) {
        console.error('Update error:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// 异步更新 overall 统计
async function updateOverallStatsAsync(user) {
    const key = getUserKey(user);
    const allData = await redis.hgetall(key);

    let totalAttempts = 0, totalCorrect = 0, totalWrong = 0;

    for (const [field, value] of Object.entries(allData)) {
        if (field.startsWith('q:')) {
            const q = JSON.parse(value);
            totalAttempts += q.attempts || 0;
            totalCorrect += q.correctCount || 0;
            totalWrong += q.wrongCount || 0;
        }
    }

    const overall = {
        totalAttempts,
        totalCorrect,
        totalWrong,
        accuracy: totalAttempts > 0 ? Math.round((totalCorrect / totalAttempts) * 100) : 0,
        lastUpdate: new Date().toISOString()
    };

    await redis.hset(key, 'overall', JSON.stringify(overall));
    return overall;
}

// 更新总体统计（本地模式）
function updateOverallStats(userStats) {
    if (!userStats.questions) return;

    let totalAttempts = 0, totalCorrect = 0, totalWrong = 0;
    for (const q of Object.values(userStats.questions)) {
        totalAttempts += q.attempts || 0;
        totalCorrect += q.correctCount || 0;
        totalWrong += q.wrongCount || 0;
    }

    userStats.overall = {
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

        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            const stats = JSON.parse(data);
            res.json(stats.users?.[user]?.questions?.[questionId] || {});
        } else {
            const data = await redis.hget(getUserKey(user), getQuestionField(questionId));
            res.json(data ? JSON.parse(data) : {});
        }
    } catch (err) {
        res.json({});
    }
});

// 论文评审记录
const ESSAY_RECORDS_FILE = path.join(DATA_DIR, 'essay_records.json');
if (isLocal && !fs.existsSync(ESSAY_RECORDS_FILE)) {
    fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify({ records: [] }, null, 2));
}

app.get('/api/essay/questions', async (req, res) => {
    try {
        const questionsData = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions_data.json'), 'utf8'));
        const essayMock = questionsData.mock_exams?.['论文'] || {};
        const questions = [];

        for (const examName of Object.keys(essayMock)) {
            for (const q of essayMock[examName]) {
                const titleMatch = q.content.match(/请围绕["""](.+?)["""]论题/) ||
                                   q.content.match(/论(.+?)\s*应用/);
                questions.push({
                    id: q.id,
                    title: titleMatch ? titleMatch[1].trim() : `论文题 ${q.id}`,
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

app.post('/api/essay/review', async (req, res) => {
    try {
        const { questionId, abstract, content } = req.body;
        if (!abstract || !content) {
            return res.status(400).json({ success: false, error: '摘要和正文不能为空' });
        }

        const questionsData = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions_data.json'), 'utf8'));
        const essayMock = questionsData.mock_exams?.['论文'] || {};
        let question = null;

        for (const qList of Object.values(essayMock)) {
            question = qList.find(q => q.id === questionId);
            if (question) break;
        }

        if (!question) {
            return res.status(400).json({ success: false, error: '题目不存在' });
        }

        const review = await reviewEssay(question, abstract, content);
        if (!review.success) {
            return res.status(500).json({ success: false, error: review.error });
        }

        const record = {
            id: Date.now().toString(36) + Math.random().toString(36).substr(2, 5),
            questionId,
            questionTitle: question.content.match(/请围绕["""](.+?)["""]论题/)?.[1] || `论文题 ${questionId}`,
            abstract, content,
            review: review.result,
            createdAt: new Date().toISOString()
        };

        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            const records = JSON.parse(data);
            records.records.unshift(record);
            if (records.records.length > 100) records.records = records.records.slice(0, 100);
            fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify(records, null, 2));
            res.json({ success: true, record, usage: review.usage });
        } else {
            const data = await redis.get('essay_records');
            const records = data ? JSON.parse(data) : { records: [] };
            records.records.unshift(record);
            if (records.records.length > 100) records.records = records.records.slice(0, 100);
            await redis.set('essay_records', JSON.stringify(records));
            res.json({ success: true, record, usage: review.usage });
        }
    } catch (err) {
        console.error('Essay review error:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

app.get('/api/essay/records', async (req, res) => {
    try {
        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            res.json({ success: true, records: JSON.parse(data).records });
        } else {
            const data = await redis.get('essay_records');
            res.json({ success: true, records: data ? JSON.parse(data).records : [] });
        }
    } catch (err) {
        res.json({ success: true, records: [] });
    }
});

app.delete('/api/essay/records/:id', async (req, res) => {
    try {
        if (isLocal) {
            const data = fs.readFileSync(ESSAY_RECORDS_FILE, 'utf8');
            const records = JSON.parse(data);
            records.records = records.records.filter(r => r.id !== req.params.id);
            fs.writeFileSync(ESSAY_RECORDS_FILE, JSON.stringify(records, null, 2));
        } else {
            const data = await redis.get('essay_records');
            const records = data ? JSON.parse(data) : { records: [] };
            records.records = records.records.filter(r => r.id !== req.params.id);
            await redis.set('essay_records', JSON.stringify(records));
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