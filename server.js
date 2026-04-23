const express = require('express');
const fs = require('fs');
const path = require('path');
const { Redis } = require('@upstash/redis');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

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

if (isLocal && !fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}

if (isLocal && !fs.existsSync(STATS_FILE)) {
    fs.writeFileSync(STATS_FILE, JSON.stringify({}, null, 2));
}

app.use(express.static(__dirname));

// 获取统计数据
app.get('/api/stats', async (req, res) => {
    try {
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            res.json(JSON.parse(data));
        } else {
            const data = await redis.get('stats');
            res.json(data || {});
        }
    } catch (err) {
        res.json({});
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

        let stats;
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            stats = JSON.parse(data);
        } else {
            stats = await redis.get('stats') || {};
        }

        if (!stats.questions) stats.questions = {};
        stats.questions[questionId] = {
            ...stats.questions[questionId],
            ...record,
            lastUpdate: new Date().toISOString()
        };

        updateOverallStats(stats);

        if (isLocal) {
            fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2));
        } else {
            await redis.set('stats', stats);
        }

        res.json({ success: true, stats });
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
        let stats;
        if (isLocal) {
            const data = fs.readFileSync(STATS_FILE, 'utf8');
            stats = JSON.parse(data);
        } else {
            stats = await redis.get('stats') || {};
        }
        res.json(stats.questions?.[questionId] || {});
    } catch (err) {
        res.json({});
    }
});

app.listen(PORT, () => {
    console.log(`刷题系统服务器运行在 http://localhost:${PORT}`);
});

module.exports = app;