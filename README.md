
# 🎓 NextGen Learners — AI Campus Intelligence System

An intelligent Agentic AI web application for student performance prediction and smart campus recommendations, built with Flask + OpenAI GPT-4.

---

## 🚀 Quick Start

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 - Set Open API Key
```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Step 3 — Run the app

```bash
python app.py
```

### Step 4 — Open in browser

```
http://localhost:5000
```
---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Dashboard** | Campus-wide stats, performance distribution, subject averages |
| 👥 **Student Profiles** | Module-level drill-down with scores, attendance, study hours |
| ⚠️ **At-Risk Monitor** | Auto-flagged students needing intervention |
| 🤖 **AI Advisor Chat** | GPT-4 powered chat with full student context |
| 📅 **Study Plans** | Auto-generated personalized weekly study plans |
| 🔮 **Predictions** | AI analysis of future performance risk |

---

## 🤖 AI Agent Capabilities

The AI Advisor (powered by OpenAI GPT-4) can:

- **Generate personalized study plans** based on weak modules
- **Identify at-risk students** with detailed factor analysis
- **Predict performance trajectories** from current data patterns
- **Recommend campus resources** (tutoring, labs, library)
- **Create improvement roadmaps** (daily/weekly goals)
- **Analyze subject-level weaknesses** across all 9 modules

---

## 📊 Dataset Info

- **120 students** (S101–S220)
- **3 subjects**: Math, CS, English
- **3 modules each**: 9 modules total per student
- **Fields per module**: score, attendance, study hours, assignment score, quiz score
- **Summary fields**: avg_score, performance_category (High/Medium/Low), at_risk (Yes/No)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS (dark theme) |
| Backend | Python 3, Flask |
| AI | OpenAI GPT-4o-mini via API |
| Data | Pandas, openpyxl |
| Charts | Canvas API |

---


