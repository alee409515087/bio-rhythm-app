# Bio-Rhythm Analytics Engine

> Project 5 實作：認知節律分析儀表板  
> Tech Stack: Python Flask · SQLite · Vanilla JS

---

## Project 5 對照

| 題目要求 | 實作對應 | 狀態 |
|---|---|---|
| Heatmap Grid（X 軸 = 小時，Y 軸 = 星期）| `dashboard.js` `renderHeatmap()` | ✅ |
| 顏色編碼（深綠 = 高效能，紅 = 低效能）| `scoreToColor()` 紅→琥珀→綠插值 | ✅ |
| Branch / Team / Agent 三層下拉篩選 | 左側聯動篩選器 + `/api/teams` `/api/agents` | ✅ |
| Actionable Insights sidebar | 右側洞察欄，自動生成文字建議 | ✅ |
| Batch Job（不直接查原始資料）| APScheduler 每 2 分鐘重算 `hourly_bio_aggregates` | ✅ |
| Bio-Score 加權公式（速度 > 慢速）| `bio_score.py` `calculate_bio_score()` | ✅ |
| Cold Start Protocol（< 10 模組套用分行平均）| `database.py` `get_heatmap_data()` | ✅ |
| `AgentProfiles` 資料表（含 peak_hour / peak_day）| `database.py` `init_db()` | ✅ |
| `ModuleDifficultyBaseline` 資料表 | `database.py` `init_db()` | ✅ |
| `HourlyBioAggregates` 資料表（含 data_points_count）| `database.py` `init_db()` | ✅ |

---

## 關於示範資料

本專案專注於 Project 5 的分析與視覺化層。示範資料（`seed_data.py`）模擬業務員在不同時段的學習行為，以 Gaussian 曲線反映人類自然存在的認知節律差異——有人早上思緒最清晰，有人在下午客戶拜訪後才進入狀態。

若串接真實的學習平台，`seed_data.py` 可直接移除，系統會自動從實際的測驗紀錄中建立每位業務員的節律檔案。

---

## 快速啟動

### 1. 安裝套件
```bash
pip install -r requirements.txt
```

### 2. 啟動應用
```bash
python run.py
```

### 3. 開啟瀏覽器
```
http://localhost:5000
```

---

## 帳號說明

| 角色 | 帳號 | 密碼 | 說明 |
|---|---|---|---|
| Manager | `manager` | `manager123` | 可看全部分行/業務員儀表板 |
| 業務員 | `agent01` | `agent123` | 林志豪（晨峰型，大量資料）|
| 業務員 | `agent02` | `agent123` | 陳美君（午後型）|
| 業務員 | `agent03` | `agent123` | 王建國（寬鬆晨型）|
| 業務員 | `agent04` | `agent123` | 張雅婷（❄ 冷啟動，資料不足）|
| 業務員 | `agent05` | `agent123` | 劉志明（早上型）|
| 業務員 | `agent06` | `agent123` | 黃淑芬（下午型）|
| 業務員 | `agent07` | `agent123` | 吳俊傑（彈性中午型）|
| 業務員 | `agent08` | `agent123` | 蔡麗玲（❄ 冷啟動，資料不足）|

---

## 系統架構

```
bio-rhythm-app/
├── run.py              # 啟動腳本（一鍵啟動）
├── app.py              # Flask 路由 + APScheduler
├── database.py         # DB 查詢（heatmap / insights / cold-start）
├── bio_score.py        # Bio-Score 演算法 + 批次聚合 job
├── seed_data.py        # 模擬資料（替代尚未實作的學習端）
├── bio_rhythm.db       # SQLite（自動建立）
├── requirements.txt
├── templates/
│   ├── base.html       # 共用 layout（topbar）
│   ├── login.html      # 登入頁
│   ├── dashboard.html  # Manager 儀表板
│   └── agent.html      # 業務員個人節律頁
└── static/
    ├── css/style.css   # 深色金融終端機 UI
    └── js/dashboard.js # 熱力圖渲染、tooltip、三層篩選
```

---

## 技術選型

| 技術 | 選擇原因 |
|---|---|
| Python Flask | 輕量、快速原型、適合單一功能分析服務 |
| SQLite | 零設定、單檔案、符合題目要求的關聯式資料庫 |
| APScheduler | 在 Flask 內嵌模擬 cron job，不需額外部署排程服務 |
| Vanilla JS | 無需打包工具，降低環境依賴，瀏覽器直接執行 |

---

## 資料庫 Schema（符合 Project 5 規格）

| 資料表 | 說明 |
|---|---|
| `branches` | 分行（信義、大安）|
| `teams` | 小組（壽險銷售、法遵合規、財富管理、數位通路）|
| `agent_profiles` | 業務員基本資料 + 計算出的高峰時段 |
| `module_difficulty_baseline` | 模組平均完成時間、通過率（Bio-Score 正規化用）|
| `quiz_attempts` | 原始測驗紀錄（agent, module, time, score, tab_switches）|
| `hourly_bio_aggregates` | **熱力圖資料來源**：每人每（星期幾 × 小時）的 Bio-Score |
| `users` | 帳號（manager / agent 角色）|

---

## Bio-Score 演算法

```
Bio-Score = (accuracy × 0.50) + (speed × 0.35) + (focus × 0.15)

accuracy = quiz_score / 100
speed    = min(avg_module_time / completion_time, 1.5) / 1.5
focus    = max(0, 1 - tab_switches / 8)

最終分數 0–100
```

**設計理由**：
- `accuracy 50%`：核心學習成效
- `speed 35%`：3 分鐘得 100 分 > 6 分鐘得 100 分（符合規格要求）
- `focus 15%`：8 次以上切換 tab → focus score 歸零

---

## Cold Start 冷啟動

- 測驗紀錄 < 10 次的業務員判定為冷啟動
- 熱力圖自動回退為**所在分行平均節律**
- 業務員頁面顯示進度條（N/10 模組）
- Manager 洞察面板顯示冷啟動人數警示

---

## Batch Job

- 使用 `APScheduler` 每 **2 分鐘**自動重算 `hourly_bio_aggregates`
- 模擬生產環境 cron job（e.g. 每日凌晨重算）
- Dashboard sidebar 顯示運行狀態指示燈
