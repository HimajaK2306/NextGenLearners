from flask import Flask, render_template, request, jsonify
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from openai import OpenAI

app = Flask(__name__)

# ── API Key (hardcoded) ───────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATA_PATH     = os.path.join(os.path.dirname(__file__), 'data', 'combined_student_dataset.xlsx')
ADAPTIVE_DIR  = os.path.join(os.path.dirname(__file__), 'data', 'adaptive')
os.makedirs(ADAPTIVE_DIR, exist_ok=True)

# ── Smart reminders schedule ──────────────────────────────────────────────────
REMINDERS = {
    "Math": [
        {"type": "Exam",       "subject": "Math",    "topic": "Algebra Mid-Term",         "due_days": 5},
        {"type": "Assignment", "subject": "Math",    "topic": "Calculus Problem Set 3",   "due_days": 2},
        {"type": "Quiz",       "subject": "Math",    "topic": "Trigonometry Quiz",         "due_days": 8},
        {"type": "Exam",       "subject": "Math",    "topic": "Calculus Unit Test",        "due_days": 20},
    ],
    "CS": [
        {"type": "Assignment", "subject": "CS",      "topic": "Data Structures Lab Report","due_days": 3},
        {"type": "Exam",       "subject": "CS",      "topic": "DBMS Final Exam",           "due_days": 25},
        {"type": "Quiz",       "subject": "CS",      "topic": "OS Concepts Quiz",          "due_days": 7},
        {"type": "Exam",       "subject": "CS",      "topic": "Data Structures Mid-Term",  "due_days": 14},
        {"type": "Assignment", "subject": "CS",      "topic": "DBMS Assignment 4",         "due_days": 10},
    ],
    "English": [
        {"type": "Assignment", "subject": "English", "topic": "Essay Submission Topic 2",  "due_days": 6},
        {"type": "Exam",       "subject": "English", "topic": "Comprehension Test",        "due_days": 8},
        {"type": "Quiz",       "subject": "English", "topic": "Grammar Quiz",              "due_days": 4},
        {"type": "Quiz",       "subject": "English", "topic": "Writing Skills Quiz",       "due_days": 17},
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENT ADAPTIVE LEARNING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _adaptive_path(student_id):
    return os.path.join(ADAPTIVE_DIR, f"{student_id}.json")


def load_adaptive(student_id):
    """Load full adaptive profile for a student from disk."""
    path = _adaptive_path(student_id)
    if not os.path.exists(path):
        return _new_adaptive_profile(student_id)
    with open(path, 'r') as f:
        return json.load(f)


def save_adaptive(student_id, profile):
    """Persist adaptive profile to disk."""
    with open(_adaptive_path(student_id), 'w') as f:
        json.dump(profile, f, indent=2)


def _new_adaptive_profile(student_id):
    """Create a blank adaptive profile for a new student."""
    return {
        "student_id":        student_id,
        "created_at":        datetime.now().isoformat(),
        "total_sessions":    0,
        "sessions":          [],          # full session log
        "covered_topics":    [],          # topics already studied
        "mastered_topics":   [],          # topics where progress noted
        "struggling_topics": [],          # topics flagged as persistent weak
        "progress_log":      [],          # weekly progress entries
        "last_focus":        None,        # last session's main topic
        "streak_days":       0,           # consecutive days active
        "last_active":       None,
        "goals": {
            "week_target":   65,          # target avg score for this week
            "month_target":  75,
        },
        "recommendations_given": [],      # track what was already recommended
    }


def update_adaptive_profile(student_id, message, reply):
    """
    Full adaptive learning update after each interaction.
    Tracks: topics covered, focus areas, progress signals,
    struggling patterns, streak, and what was already recommended.
    """
    profile = load_adaptive(student_id)
    now     = datetime.now()

    # ── Extract topics mentioned ──────────────────────────────────────────────
    module_keywords = {
        "algebra":           "Math",
        "calculus":          "Math",
        "trigonometry":      "Math",
        "dbms":              "CS",
        "data structures":   "CS",
        "operating systems": "CS",
        "grammar":           "English",
        "writing":           "English",
        "comprehension":     "English",
    }
    combined = (message + " " + reply).lower()
    topics_this_session = [k.title() for k in module_keywords if k in combined]

    # ── Detect focus type ─────────────────────────────────────────────────────
    focus = (
        "study_plan"          if "study plan"   in combined else
        "performance_analysis" if "performance" in combined else
        "reminder"            if "reminder"     in combined or "exam" in combined else
        "resources"           if "resource"     in combined or "lab"  in combined else
        "progress_check"      if "progress"     in combined or "improve" in combined else
        "general"
    )

    # ── Detect progress signals in reply ─────────────────────────────────────
    progress_signals = []
    if any(w in combined for w in ["improved", "better", "stronger", "good progress", "well done"]):
        progress_signals.append("positive_progress")
    if any(w in combined for w in ["still weak", "needs more", "critical", "urgent", "at risk"]):
        progress_signals.append("still_struggling")
    if any(w in combined for w in ["mastered", "excellent", "high priority resolved"]):
        progress_signals.append("mastered")

    # ── Update covered / struggling / mastered ────────────────────────────────
    for topic in topics_this_session:
        if topic not in profile["covered_topics"]:
            profile["covered_topics"].append(topic)

    # Topics covered 3+ times without mastery = struggling
    topic_freq = {}
    for s in profile["sessions"]:
        for t in s.get("topics", []):
            topic_freq[t] = topic_freq.get(t, 0) + 1
    for topic, freq in topic_freq.items():
        if freq >= 3 and topic not in profile["mastered_topics"]:
            if topic not in profile["struggling_topics"]:
                profile["struggling_topics"].append(topic)

    if "mastered" in progress_signals:
        for topic in topics_this_session:
            if topic not in profile["mastered_topics"]:
                profile["mastered_topics"].append(topic)
            if topic in profile["struggling_topics"]:
                profile["struggling_topics"].remove(topic)

    # ── Track what recommendations were given ─────────────────────────────────
    rec_keywords = ["math tutoring lab", "cs lab", "writing center",
                    "library", "academic counseling", "khan academy",
                    "coursera", "peer study group"]
    for rk in rec_keywords:
        if rk in reply.lower() and rk not in profile["recommendations_given"]:
            profile["recommendations_given"].append(rk)

    # ── Streak tracking ───────────────────────────────────────────────────────
    if profile["last_active"]:
        last_date = datetime.fromisoformat(profile["last_active"]).date()
        today     = now.date()
        if (today - last_date).days == 1:
            profile["streak_days"] = profile.get("streak_days", 0) + 1
        elif (today - last_date).days > 1:
            profile["streak_days"] = 1   # reset streak
    else:
        profile["streak_days"] = 1

    # ── Build session record ──────────────────────────────────────────────────
    session_record = {
        "session_number": profile["total_sessions"] + 1,
        "timestamp":      now.isoformat(),
        "date":           now.strftime("%Y-%m-%d"),
        "focus":          focus,
        "topics":         topics_this_session,
        "progress":       progress_signals,
        "message_preview":message[:120],
    }

    profile["sessions"].append(session_record)
    profile["sessions"]    = profile["sessions"][-20:]    # keep last 20
    profile["total_sessions"] += 1
    profile["last_focus"]   = focus
    profile["last_active"]  = now.isoformat()

    save_adaptive(student_id, profile)
    return profile


def get_adaptive_context(student_id):
    """
    Build a rich adaptive context string for the system prompt.
    Tells the AI exactly what was covered, what to build on,
    and what NOT to repeat.
    """
    profile = load_adaptive(student_id)

    if profile["total_sessions"] == 0:
        return "\nADAPTIVE LEARNING: First session for this student — start with a full assessment.\n"

    sessions    = profile["sessions"]
    recent      = sessions[-3:]
    all_topics  = profile["covered_topics"]
    struggling  = profile["struggling_topics"]
    mastered    = profile["mastered_topics"]
    recs_given  = profile["recommendations_given"]
    streak      = profile["streak_days"]
    total       = profile["total_sessions"]
    last_focus  = profile["last_focus"]

    ctx  = f"\n{'='*60}\n"
    ctx += f"ADAPTIVE LEARNING PROFILE — {student_id}\n"
    ctx += f"{'='*60}\n"
    ctx += f"Total sessions: {total}  |  Current streak: {streak} day(s)  |  Last focus: {last_focus}\n\n"

    # Recent sessions
    ctx += "RECENT SESSION HISTORY (last 3 sessions):\n"
    for s in recent:
        ctx += (f"  Session {s['session_number']} | {s['date']} | "
                f"Focus: {s['focus']} | Topics: {', '.join(s['topics']) or 'general'} | "
                f"Progress: {', '.join(s['progress']) or 'neutral'}\n")

    # Covered topics
    if all_topics:
        ctx += f"\nTOPICS ALREADY COVERED (do NOT repeat basic advice on these):\n"
        ctx += f"  {', '.join(all_topics)}\n"

    # Struggling topics
    if struggling:
        ctx += f"\nPERSISTENTLY STRUGGLING (covered 3+ times — needs DEEPER approach):\n"
        ctx += f"  {', '.join(struggling)}\n"
        ctx += f"  ACTION: Switch strategy — try different explanation, practice method, or resource\n"

    # Mastered topics
    if mastered:
        ctx += f"\nMODULES SHOWING PROGRESS (acknowledge improvement):\n"
        ctx += f"  {', '.join(mastered)}\n"

    # Resources already recommended
    if recs_given:
        ctx += f"\nRESOURCES ALREADY RECOMMENDED (suggest NEW ones if possible):\n"
        ctx += f"  {', '.join(recs_given)}\n"

    # Adaptive instruction for the AI
    ctx += "\nADAPTIVE INSTRUCTIONS FOR THIS SESSION:\n"
    if total == 1:
        ctx += "  - Second session: build on first session's study plan. Ask how Day 1-3 went.\n"
    elif total <= 3:
        ctx += "  - Early sessions: check progress on previously set goals before adding new advice.\n"
    elif total <= 7:
        ctx += "  - Mid sessions: go DEEPER into struggling topics. Introduce advanced practice methods.\n"
    else:
        ctx += "  - Long-term student: focus on fine-tuning and mastery. Celebrate progress.\n"

    if struggling:
        ctx += f"  - {', '.join(struggling)} need a DIFFERENT approach this session — not the same advice again.\n"

    if streak >= 3:
        ctx += f"  - Student has a {streak}-day streak! Acknowledge consistency and encourage them.\n"

    if last_focus == "study_plan":
        ctx += "  - Last session was a study plan. This session: CHECK IN on progress, don't just give another plan.\n"
    elif last_focus == "reminder":
        ctx += "  - Last session was about reminders. This session: follow up on whether deadlines were met.\n"

    ctx += f"{'='*60}\n"
    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_data():
    module_df  = pd.read_excel(DATA_PATH, sheet_name='Module_Data')
    summary_df = pd.read_excel(DATA_PATH, sheet_name='Student_Summary')
    return module_df, summary_df


def get_student_context(student_id):
    module_df, summary_df = load_data()
    student_modules = module_df[module_df['student_id'] == student_id]
    student_summary = summary_df[summary_df['student_id'] == student_id]
    if student_modules.empty:
        return None, None

    summary_row    = student_summary.iloc[0] if not student_summary.empty else {}
    weak_modules   = student_modules[student_modules['module_score'] < 60]
    low_att        = student_modules[student_modules['attendance_percentage'] < 65]
    strong_modules = student_modules[student_modules['module_score'] >= 75]

    context = f"""
STUDENT DATASET CONTEXT:
Student ID: {student_id}
Performance: {summary_row.get('performance_category','Unknown')} | Avg Score: {summary_row.get('avg_score','Unknown')} | At Risk: {summary_row.get('at_risk','Unknown')}

WEAK MODULES (score < 60) — HIGH PRIORITY:
"""
    for _, row in weak_modules.iterrows():
        context += f"  WEAK: {row['subject_name']} -> {row['module_name']}: {row['module_score']}/100 | Att:{row['attendance_percentage']}% | Assign:{row['assignment_score']} | Quiz:{row['quiz_score']}\n"

    context += "\nCRITICAL LOW ATTENDANCE (< 65%):\n"
    if low_att.empty:
        context += "  None\n"
    else:
        for _, row in low_att.iterrows():
            context += f"  CRITICAL: {row['subject_name']} -> {row['module_name']}: {row['attendance_percentage']}%\n"

    context += "\nSTRONG MODULES (score >= 75):\n"
    for _, row in strong_modules.iterrows():
        context += f"  GOOD: {row['subject_name']} -> {row['module_name']}: {row['module_score']}/100\n"

    context += "\nFULL BREAKDOWN:\n"
    for _, row in student_modules.iterrows():
        status = "WEAK" if row['module_score'] < 60 else ("OK" if row['module_score'] < 75 else "GOOD")
        context += (f"  {row['subject_name']} | {row['module_name']} | "
                    f"Score:{row['module_score']} | Att:{row['attendance_percentage']}% | "
                    f"StudyHrs:{row['study_hours_per_week']} | Assign:{row['assignment_score']} | Quiz:{row['quiz_score']} | {status}\n")
    return context, student_summary


def get_reminders_for_student(student_id):
    module_df, _ = load_data()
    student_modules = module_df[module_df['student_id'] == student_id]
    if student_modules.empty:
        return []
    weak_subjects = student_modules[student_modules['module_score'] < 60]['subject_name'].unique().tolist()
    reminders = []
    today = datetime.today()
    for subject in weak_subjects:
        if subject in REMINDERS:
            for r in REMINDERS[subject]:
                due_date = today + timedelta(days=r['due_days'])
                urgency  = "URGENT" if r['due_days'] <= 2 else ("SOON" if r['due_days'] <= 7 else "UPCOMING")
                reminders.append({
                    "urgency":  urgency,
                    "type":     r['type'],
                    "subject":  r['subject'],
                    "topic":    r['topic'],
                    "due_date": due_date.strftime("%A, %d %b %Y"),
                    "due_days": r['due_days'],
                })
    reminders.sort(key=lambda x: x['due_days'])
    return reminders


def get_faculty_context():
    module_df, summary_df = load_data()
    at_risk_df   = summary_df[summary_df['at_risk'] == 'Yes']
    subject_avgs = module_df.groupby('subject_name')['module_score'].mean().round(2).to_dict()
    weakest      = min(subject_avgs, key=subject_avgs.get)
    ctx = f"""
FACULTY DASHBOARD:
Total: {len(summary_df)} | At-Risk: {len(at_risk_df)} | Low: {len(summary_df[summary_df['performance_category']=='Low'])}
Subject Averages: {subject_avgs} | Weakest Subject: {weakest}

AT-RISK DETAILS:
"""
    for _, s in at_risk_df.iterrows():
        sid  = s['student_id']
        mods = module_df[module_df['student_id'] == sid]
        weak = mods[mods['module_score'] < 60].sort_values('module_score')
        low_a = mods[mods['attendance_percentage'] < 65]
        ctx += f"\n  {sid} | Avg:{s['avg_score']} | {s['performance_category']}\n"
        ctx += "    Weak: " + ", ".join([f"{r['subject_name']}/{r['module_name']}({r['module_score']})" for _,r in weak.iterrows()]) + "\n"
        if not low_a.empty:
            ctx += "    LowAtt: " + ", ".join([f"{r['subject_name']}/{r['module_name']}({r['attendance_percentage']}%)" for _,r in low_a.iterrows()]) + "\n"
    return ctx


def get_admin_context():
    module_df, summary_df = load_data()
    subject_avgs = module_df.groupby('subject_name')['module_score'].mean().round(2).to_dict()
    subject_weak = {s: int(len(g[g['module_score']<60])) for s,g in module_df.groupby('subject_name')}
    at_risk      = summary_df[summary_df['at_risk']=='Yes']['student_id'].tolist()
    n = len(summary_df)
    return f"""
ADMIN ANALYTICS:
Total:{n} | Avg:{summary_df['avg_score'].mean():.2f}
High:{len(summary_df[summary_df['performance_category']=='High'])} ({len(summary_df[summary_df['performance_category']=='High'])/n*100:.1f}%)
Medium:{len(summary_df[summary_df['performance_category']=='Medium'])} ({len(summary_df[summary_df['performance_category']=='Medium'])/n*100:.1f}%)
Low:{len(summary_df[summary_df['performance_category']=='Low'])} ({len(summary_df[summary_df['performance_category']=='Low'])/n*100:.1f}%)
At-Risk({len(at_risk)}): {', '.join(at_risk)}
SubjectAvg: {subject_avgs}
WeakCounts: {subject_weak}
Top5: {summary_df.nlargest(5,'avg_score')[['student_id','avg_score']].to_dict('records')}
Bottom5: {summary_df.nsmallest(5,'avg_score')[['student_id','avg_score']].to_dict('records')}
"""


def get_all_students():
    _, summary_df = load_data()
    return summary_df.to_dict('records')


def get_dashboard_stats():
    module_df, summary_df = load_data()
    return {
        'total_students':    len(summary_df),
        'at_risk_count':     int(len(summary_df[summary_df['at_risk']=='Yes'])),
        'high_performers':   int(len(summary_df[summary_df['performance_category']=='High'])),
        'medium_performers': int(len(summary_df[summary_df['performance_category']=='Medium'])),
        'low_performers':    int(len(summary_df[summary_df['performance_category']=='Low'])),
        'avg_score':         round(float(summary_df['avg_score'].mean()), 2),
        'subject_averages':  module_df.groupby('subject_name')['module_score'].mean().round(2).to_dict(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def build_student_prompt(student_context, adaptive_context, reminders):
    reminder_block = ""
    if reminders:
        reminder_block = "\nSMART REMINDERS — mention these proactively:\n"
        for r in reminders[:6]:
            reminder_block += (f"  [{r['urgency']}] {r['type']}: {r['topic']} ({r['subject']}) "
                               f"— Due {r['due_date']} ({r['due_days']} days away)\n")

    return f"""You are an intelligent AI Academic Advisor for NextGen Learners campus.

{student_context}
{adaptive_context}
{reminder_block}

YOUR CORE RESPONSIBILITIES:
1. PERFORMANCE PREDICTION — analyze scores, attendance, quiz/assignment data
2. WEAK MODULE DETECTION — score < 60 = HIGH PRIORITY | attendance < 65% = CRITICAL
3. PERSONALIZED STUDY PLAN — Day | Subject | Module | Task | Hours | Goal
4. ADAPTIVE RECOMMENDATIONS — CRITICAL: use the adaptive history above.
   - Do NOT repeat advice already given in previous sessions
   - If a topic appears in "PERSISTENTLY STRUGGLING" use a completely different approach
   - If student has a streak, acknowledge it
   - Check in on previous goals before setting new ones
5. SMART REMINDERS — proactively alert about upcoming deadlines

CAMPUS RESOURCES:
   Math      → Math Tutoring Lab, Room 101, Mon-Fri 9am-5pm
   CS        → CS Lab, Room 205, Mon-Thu 10am-6pm
   English   → Writing Center, Room 115, Tue/Thu 2pm-6pm
   General   → Library 24/7, Building A
   At-risk   → Academic Counseling, Admin Block
   Online    → Khan Academy, Coursera, MIT OpenCourseWare

Always use actual scores and module names. End with 3 clear next steps."""


def build_faculty_prompt(ctx):
    return f"""You are a Faculty Support Assistant for NextGen Learners campus.
{ctx}
Responsibilities: at-risk identification, double-risk alerts (low score + low attendance),
intervention plans, subject analytics, class performance trends.
Flag students scoring < 50 for one-on-one sessions.
Flag attendance < 60% for mandatory tutoring referral.
Be concise, professional, data-driven."""


def build_admin_prompt(ctx):
    return f"""You are a Campus Analytics Assistant for NextGen Learners.
{ctx}
Responsibilities: campus overview with percentages, at-risk report, subject rankings,
top/bottom performers, resource recommendations, predictive insights,
strategic recommendations for next semester.
Use headings, numbers, percentages. Be executive-level."""


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html', stats=get_dashboard_stats(), students=get_all_students())


@app.route('/api/chat', methods=['POST'])
def chat():
    data         = request.json
    user_message = data.get('message', '')
    student_id   = data.get('student_id', '').upper()
    role         = data.get('role', 'student').lower()
    api_key      = OPENAI_API_KEY
    history      = data.get('history', [])

    try:
        client = OpenAI(api_key=api_key)

        if role == 'faculty':
            system_prompt = build_faculty_prompt(get_faculty_context())

        elif role == 'admin':
            system_prompt = build_admin_prompt(get_admin_context())

        else:
            if student_id:
                student_context, _ = get_student_context(student_id)
                if not student_context:
                    return jsonify({'error': f'Student {student_id} not found'}), 404
            else:
                _, summary_df = load_data()
                at_risk = summary_df[summary_df['at_risk'] == 'Yes']['student_id'].tolist()
                student_context = f"""
GENERAL CAMPUS CONTEXT:
Total Students: {len(summary_df)} | Campus Avg: {summary_df['avg_score'].mean():.2f}
At-Risk: {', '.join(at_risk)}
Provide your student ID for personalized analysis."""

            adaptive_context = get_adaptive_context(student_id) if student_id else ""
            reminders        = get_reminders_for_student(student_id) if student_id else []
            system_prompt    = build_student_prompt(student_context, adaptive_context, reminders)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-10:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1800,
            temperature=0.7,
        )
        reply = response.choices[0].message.content

        # Update persistent adaptive profile
        if role == 'student' and student_id:
            profile = update_adaptive_profile(student_id, user_message, reply)
            adaptive_summary = {
                "total_sessions":    profile["total_sessions"],
                "streak_days":       profile["streak_days"],
                "covered_topics":    profile["covered_topics"],
                "struggling_topics": profile["struggling_topics"],
                "mastered_topics":   profile["mastered_topics"],
            }
        else:
            adaptive_summary = {}

        return jsonify({
            'reply':            reply,
            'tokens_used':      response.usage.total_tokens,
            'role':             role,
            'reminders':        get_reminders_for_student(student_id) if student_id else [],
            'adaptive_summary': adaptive_summary,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agent-chat', methods=['POST'])
def agent_chat():
    """
    Agent Builder integration using the Responses API.
    The workflow_id is used to identify the workflow and its instructions
    are replicated here to match the Agent Builder behavior exactly.
    Falls back gracefully with auto-detection.
    """
    data         = request.json
    user_message = data.get('message', '')
    student_id   = data.get('student_id', '').upper()
    role         = data.get('role', 'student').lower()
    api_key      = OPENAI_API_KEY
    workflow_id  = data.get('workflow_id', '').strip()

    if not api_key:
        return jsonify({'error': 'Please enter your OpenAI API key'}), 400
    if not workflow_id:
        return jsonify({'error': 'Please enter your Agent Builder Workflow ID'}), 400

    # Build full input matching Agent Builder Start node variables
    if student_id:
        full_input = f"[Student ID: {student_id}] [Role: {role}] {user_message}"
    else:
        full_input = f"[Role: {role}] {user_message}"

    reply     = ""
    run_id    = ""
    used_mode = "agent_builder"

    try:
        client = OpenAI(api_key=api_key)

        # ── Build context matching Agent Builder workflow ──────────────────
        if role == 'faculty':
            system_instructions = build_faculty_prompt(get_faculty_context())
        elif role == 'admin':
            system_instructions = build_admin_prompt(get_admin_context())
        else:
            if student_id:
                student_context, _ = get_student_context(student_id)
                if not student_context:
                    return jsonify({'error': f'Student {student_id} not found'}), 404
            else:
                _, summary_df = load_data()
                at_risk = summary_df[summary_df['at_risk'] == 'Yes']['student_id'].tolist()
                student_context = f"Campus: {len(summary_df)} students | At-Risk: {', '.join(at_risk)}"

            adaptive_context   = get_adaptive_context(student_id) if student_id else ""
            reminders_list     = get_reminders_for_student(student_id) if student_id else []
            system_instructions = build_student_prompt(student_context, adaptive_context, reminders_list)

        # ── Call via Responses API (matches Agent Builder pipeline) ────────
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=system_instructions,
            input=full_input,
            metadata={"workflow_id": workflow_id, "role": role, "student_id": student_id},
        )

        # Extract text from response
        for item in response.output:
            if hasattr(item, 'content'):
                for c in item.content:
                    if hasattr(c, 'text'):
                        reply += c.text
            elif hasattr(item, 'text'):
                reply += item.text

        if not reply:
            reply = str(response.output_text) if hasattr(response, 'output_text') else str(response.output)

        run_id    = getattr(response, 'id', workflow_id)
        used_mode = "agent_builder"

    except Exception as e:
        # Smart fallback to chat completions
        used_mode = "direct_fallback"
        try:
            client2 = OpenAI(api_key=api_key)
            if role == 'faculty':
                sys_p = build_faculty_prompt(get_faculty_context())
            elif role == 'admin':
                sys_p = build_admin_prompt(get_admin_context())
            else:
                if student_id:
                    sc, _ = get_student_context(student_id)
                else:
                    _, summary_df = load_data()
                    at_risk = summary_df[summary_df['at_risk'] == 'Yes']['student_id'].tolist()
                    sc = f"Campus: {len(summary_df)} students | At-Risk: {', '.join(at_risk)}"
                ac  = get_adaptive_context(student_id) if student_id else ""
                rem = get_reminders_for_student(student_id) if student_id else []
                sys_p = build_student_prompt(sc or "", ac, rem)

            fb = client2.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sys_p},{"role":"user","content":user_message}],
                max_tokens=1800, temperature=0.7
            )
            reply  = fb.choices[0].message.content
            run_id = f"fallback_{workflow_id[:8]}"
        except Exception as e2:
            return jsonify({'error': f'Error: {str(e2)}'}), 500

    # Update adaptive profile
    adaptive_summary = {}
    if role == 'student' and student_id:
        profile = update_adaptive_profile(student_id, user_message, reply)
        adaptive_summary = {
            "total_sessions":    profile["total_sessions"],
            "streak_days":       profile["streak_days"],
            "covered_topics":    profile["covered_topics"],
            "struggling_topics": profile["struggling_topics"],
            "mastered_topics":   profile["mastered_topics"],
        }

    return jsonify({
        'reply':            reply,
        'workflow_id':      workflow_id,
        'run_id':           run_id,
        'role':             role,
        'reminders':        get_reminders_for_student(student_id) if student_id else [],
        'adaptive_summary': adaptive_summary,
        'mode':             used_mode,
    })


@app.route('/api/student/<student_id>')
def get_student(student_id):
    module_df, summary_df = load_data()
    sid = student_id.upper()
    student_modules = module_df[module_df['student_id'] == sid]
    student_summary = summary_df[summary_df['student_id'] == sid]
    if student_modules.empty:
        return jsonify({'error': 'Student not found'}), 404
    profile = load_adaptive(sid)
    return jsonify({
        'modules':   student_modules.to_dict('records'),
        'summary':   student_summary.to_dict('records')[0] if not student_summary.empty else {},
        'reminders': get_reminders_for_student(sid),
        'adaptive':  {
            'total_sessions':    profile['total_sessions'],
            'streak_days':       profile['streak_days'],
            'covered_topics':    profile['covered_topics'],
            'struggling_topics': profile['struggling_topics'],
            'mastered_topics':   profile['mastered_topics'],
            'last_active':       profile['last_active'],
        },
    })


@app.route('/api/adaptive/<student_id>')
def get_adaptive_profile(student_id):
    """Full adaptive profile — used by UI to show learning history."""
    profile = load_adaptive(student_id.upper())
    return jsonify(profile)


@app.route('/api/adaptive/<student_id>/progress', methods=['POST'])
def log_progress(student_id):
    """Let student or faculty manually log a progress entry."""
    sid     = student_id.upper()
    data    = request.json
    profile = load_adaptive(sid)
    profile['progress_log'].append({
        "date":    datetime.now().strftime("%Y-%m-%d"),
        "module":  data.get('module', ''),
        "score":   data.get('score', 0),
        "note":    data.get('note', ''),
    })
    save_adaptive(sid, profile)
    return jsonify({'success': True, 'progress_entries': len(profile['progress_log'])})


@app.route('/api/adaptive/<student_id>/reset', methods=['POST'])
def reset_adaptive(student_id):
    """Reset adaptive profile — for testing."""
    sid = student_id.upper()
    save_adaptive(sid, _new_adaptive_profile(sid))
    return jsonify({'success': True, 'message': f'Adaptive profile reset for {sid}'})


@app.route('/api/reminders/<student_id>')
def get_reminders(student_id):
    return jsonify({'reminders': get_reminders_for_student(student_id.upper())})


@app.route('/api/faculty/at-risk')
def faculty_at_risk():
    module_df, summary_df = load_data()
    result = []
    for _, s in summary_df[summary_df['at_risk'] == 'Yes'].iterrows():
        sid  = s['student_id']
        mods = module_df[module_df['student_id'] == sid]
        weak = mods[mods['module_score'] < 60].sort_values('module_score')
        low_a = mods[mods['attendance_percentage'] < 65]
        result.append({
            'student_id':    sid,
            'avg_score':     s['avg_score'],
            'category':      s['performance_category'],
            'risk_level':    'HIGH' if s['avg_score'] < 55 else 'MEDIUM',
            'weak_modules':  weak[['subject_name','module_name','module_score']].to_dict('records'),
            'low_attendance':low_a[['subject_name','module_name','attendance_percentage']].to_dict('records'),
        })
    result.sort(key=lambda x: x['avg_score'])
    return jsonify({'at_risk_students': result, 'total': len(result)})


@app.route('/api/admin/stats')
def admin_stats():
    module_df, summary_df = load_data()
    n = len(summary_df)
    # Count adaptive sessions from disk
    adaptive_counts = {}
    for f in os.listdir(ADAPTIVE_DIR):
        if f.endswith('.json'):
            sid = f.replace('.json','')
            try:
                with open(os.path.join(ADAPTIVE_DIR, f)) as fp:
                    p = json.load(fp)
                    adaptive_counts[sid] = p.get('total_sessions', 0)
            except:
                pass
    return jsonify({
        'total_students':     n,
        'campus_average':     round(float(summary_df['avg_score'].mean()), 2),
        'at_risk_count':      int(len(summary_df[summary_df['at_risk']=='Yes'])),
        'performance_dist':   summary_df['performance_category'].value_counts().to_dict(),
        'subject_averages':   module_df.groupby('subject_name')['module_score'].mean().round(2).to_dict(),
        'weak_module_counts': {s:int(len(g[g['module_score']<60])) for s,g in module_df.groupby('subject_name')},
        'top_5':              summary_df.nlargest(5,'avg_score')[['student_id','avg_score','performance_category']].to_dict('records'),
        'bottom_5':           summary_df.nsmallest(5,'avg_score')[['student_id','avg_score','performance_category']].to_dict('records'),
        'adaptive_sessions':  adaptive_counts,
        'total_adaptive_students': len(adaptive_counts),
    })


@app.route('/api/stats')
def stats():
    return jsonify(get_dashboard_stats())


if __name__ == '__main__':
    app.run(debug=True, port=5000)
