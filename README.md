# CampusIQ

> Smart intelligence across the whole campus ecosystem.
> Student · Faculty · Admin — all in one place.

CampusIQ is a Flask web app that acts as an intelligent layer for an entire university. Students see their grades, attendance, professor info, and get an AI advisor. Faculty monitor their department's students. The campus admin gets a bird's-eye view across every department.

---

## What's inside

```
CampusIQ/
├── app.py                      # Flask backend — all routes + AI chat endpoint
├── generate_data.py            # Regenerate data/campus_data.xlsx from scratch
├── requirements.txt
├── data/
│   └── campus_data.xlsx        # Single source of truth (11 sheets, pre-generated)
└── templates/
    ├── base.html               # Shared layout + green academic theme
    ├── login.html              # 3-role login (Student / Faculty / Admin)
    ├── student_dashboard.html  # Profile + reminders + quick prompts + courses
    ├── student_course.html     # Course drill-down with instructor info
    ├── chat.html               # AI Advisor chat (uses your OpenAI API key)
    ├── faculty_dashboard.html  # Dept stats + courses taught + student roster
    ├── faculty_student_detail.html
    ├── admin_dashboard.html    # Campus-wide stats + per-dept breakdown
    └── admin_department.html   # Drill into any single department
```

---

## Quick start

```bash
cd CampusIQ
pip install -r requirements.txt

# Regenerate data (optional — campus_data.xlsx is already included)
python generate_data.py

# Run the server
python app.py
```

Open **http://localhost:5000** and sign in.

---

## Demo logins

| Role    | ID    | Password    | What they see                                    |
|---------|-------|-------------|--------------------------------------------------|
| Student | S101  | S101        | Their profile, courses, grades, AI advisor       |
| Faculty | P001  | P001        | Only students in THEIR department                |
| Admin   | ADMIN | admin123    | Campus-wide overview across all 12 departments   |

Any `S101`–`S220` works as a student (password = ID).
Any `P001`–`P036` works as faculty (password = ID).

---

## What each role sees

### 👨‍🎓 Student view
- **Dashboard** — name, department, program, year, email · semester snapshot (overall score / attendance / credits) · **Smart Reminders** with urgency colors (URGENT · SOON · UPCOMING) pulled from their weak courses · **Quick Prompts** sidebar that jumps straight into AI chat with a pre-filled question · grid of all enrolled courses with avg score, attendance, and letter grade.
- **Course detail** — instructor name, email, office, office hours · 4 headline stats (score / attendance / assignments / quizzes) · one row per module with progress bar.
- **AI Advisor** — full conversation UI with the student's own context pre-loaded. User pastes their OpenAI API key once (stored in session only) and can then ask for study plans, weak-area analysis, performance predictions, campus resources, and more.

### 👩‍🏫 Faculty view
- **Dashboard** — professor profile with office hours · 4 stat cards (Total Students / At-Risk / High Performers / Avg Dept Score) scoped to their department · "Courses I Teach" grid showing class average per course · roster of every student in their department, sorted by risk.
- **Student detail** — a professor can click any student in their department to see their full profile and enrolled courses. Students from OTHER departments are blocked with an access-denied redirect.

### 🛡️ Admin view (super-admin)
- **Campus overview** — hero with 12 departments / 68 courses / 36 faculty counts · 4 headline stats (Total Students / At-Risk / High / Avg Score) · 3 secondary stats (Avg Attendance / Medium / Low) · full department breakdown table with mini-bars, sorted by avg score.
- **Department detail** — click any department to see the same 4-stat strip scoped to that dept plus the full roster.

---

## Data model

`data/campus_data.xlsx` contains 11 sheets:

| Sheet                | Rows | Purpose                                                 |
|----------------------|------|---------------------------------------------------------|
| `Departments`        | 12   | 12 schools/departments                                  |
| `Courses`            | 68   | ~5–6 courses per department, 3 modules each             |
| `Students`           | 120  | S101–S220 with name, email, dept, program, year         |
| `Enrollments`        | 720  | Which students are in which courses                     |
| `Modules`            | 2160 | Every student × every module with score/attendance/etc. |
| `Summary`            | 120  | Per-student rollup (avg score, at-risk flag)            |
| `Professors`         | 36   | ~3 profs per dept with office, office hours, email      |
| `CourseAssignments`  | 68   | Which professor teaches which course                    |
| `Admin`              | 1    | Super-admin account                                     |
| `StudentCredentials` | 120  | Demo student logins                                     |
| `FacultyCredentials` | 36   | Demo faculty logins                                     |

All emails use `@campusiq.edu` (generic, no real-university branding).

---

## AI Advisor — how it works

1. Student opens `/student/chat` — the page checks if an API key is stored in their Flask session.
2. If not, clicking "API key required" opens a modal. User pastes an OpenAI key (must start with `sk-`). It's stored only in the server-side session — never written to disk, never logged.
3. When the student sends a message, the backend builds a rich system prompt that includes the student's real name, department, program, every enrolled course with actual grades, weak courses, strong courses, and their next 8 upcoming deadlines.
4. The message is sent to `gpt-4o-mini` via the OpenAI Responses API, along with the last 10 turns of chat history.
5. Reply streams back into the chat window.

The same endpoint works for Faculty and Admin with different system prompts (dept stats for faculty; campus-wide for admin), but the chat UI is currently only wired up for Students.

---

## Security notes

This is a **demo project**. Do not ship as-is to production:
- Passwords are plaintext in the Excel file
- Flask secret key is hardcoded
- Sessions are unsigned cookies (use `itsdangerous` + real secret in prod)
- Use real password hashing (bcrypt / argon2) and a real user table (SQLite/Postgres)

---

## Tech stack

| Layer         | Tech                                  |
|---------------|---------------------------------------|
| Backend       | Python 3, Flask                       |
| Data          | pandas, openpyxl, Excel               |
| AI            | openai (user-provided API key)        |
| Auth          | Flask sessions                        |
| Frontend      | Jinja2 + vanilla CSS (no JS framework)|
| Fonts         | Fraunces · Inter · JetBrains Mono     |

---

## Roadmap

- [x] **Student view** — login, dashboard with reminders/prompts, course drill-down with instructor, dedicated reminders page
- [x] **Faculty view** — dept-scoped dashboard with clickable stat cards (filter the roster), filters (status/year/program/search), Courses I Teach drilling into per-class rosters, student drill-down
- [x] **Admin view** — campus-wide analytics, per-dept breakdown and drill-down
- [x] **AI Advisor (student)** — GPT-4o-mini with full student context, quick prompts
- [x] **AI Assistant (faculty)** — dept-scoped quick prompts: At-Risk List, Double-Risk Alert, Subject Analytics, Intervention Plans, Class Comparison, Risk by Year
- [x] **AI Insights (admin)** — campus quick prompts: Campus Overview, Top & Bottom 5, Resource Planning, Predictive Alerts, Strategy Report, School Comparison
- [ ] Password hashing & secure session
- [ ] Persistent adaptive learning (per-student memory across chat sessions)
- [ ] Mobile native app via React Native
