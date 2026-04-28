"""
CampusIQ — Smart intelligence across the whole campus ecosystem.
Three roles: Student, Faculty, Admin (super-admin).

Run:
    pip install -r requirements.txt
    python generate_data.py      # once, or whenever you want fresh data
    python app.py                # → http://localhost:5000
"""
import os
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, flash,
)

app = Flask(__name__)
app.secret_key = "campusiq-demo-secret-change-me"   # demo only

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "campus_data.xlsx")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def load_sheet(name):
    return pd.read_excel(DATA_PATH, sheet_name=name)


def get_student(student_id):
    df = load_sheet("Students")
    row = df[df["student_id"] == student_id]
    return row.iloc[0].to_dict() if not row.empty else None


def get_professor(prof_id):
    df = load_sheet("Professors")
    row = df[df["prof_id"] == prof_id]
    return row.iloc[0].to_dict() if not row.empty else None


def get_department(dept_id):
    df = load_sheet("Departments")
    row = df[df["dept_id"] == dept_id]
    return row.iloc[0].to_dict() if not row.empty else None


def get_course_professor(course_code):
    """Return the professor assigned to teach this course, or None."""
    assigns = load_sheet("CourseAssignments")
    match = assigns[assigns["course_code"] == course_code]
    if match.empty:
        return None
    return get_professor(match.iloc[0]["prof_id"])


def score_to_grade(score):
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def score_to_color(score):
    if score >= 75: return "high"
    if score >= 60: return "medium"
    return "low"


def att_color(pct):
    if pct >= 80: return "high"
    if pct >= 65: return "medium"
    return "low"


# ═══════════════════════════════════════════════════════════════════════════════
# STUDENT DATA
# ═══════════════════════════════════════════════════════════════════════════════
def get_student_enrollments(student_id):
    enroll = load_sheet("Enrollments")
    mods   = load_sheet("Modules")
    my_enroll = enroll[enroll["student_id"] == student_id].copy()
    if my_enroll.empty:
        return []

    my_mods = mods[mods["student_id"] == student_id]
    course_stats = my_mods.groupby("course_code").agg(
        avg_score      = ("module_score",         "mean"),
        avg_attendance = ("attendance_percentage","mean"),
        avg_assignment = ("assignment_score",     "mean"),
        avg_quiz       = ("quiz_score",           "mean"),
        modules_count  = ("module_score",         "count"),
    ).reset_index()

    merged = my_enroll.merge(course_stats, on="course_code", how="left")

    out = []
    for _, r in merged.iterrows():
        avg = float(r["avg_score"]) if pd.notna(r["avg_score"]) else 0
        out.append({
            "enrollment_id":  r["enrollment_id"],
            "course_code":    r["course_code"],
            "course_title":   r["course_title"],
            "credits":        int(r["credits"]),
            "semester":       r["semester"],
            "status":         r["status"],
            "avg_score":      round(avg, 1),
            "avg_attendance": round(float(r["avg_attendance"]), 1) if pd.notna(r["avg_attendance"]) else 0,
            "avg_assignment": round(float(r["avg_assignment"]), 1) if pd.notna(r["avg_assignment"]) else 0,
            "avg_quiz":       round(float(r["avg_quiz"]), 1)       if pd.notna(r["avg_quiz"])       else 0,
            "modules_count":  int(r["modules_count"]) if pd.notna(r["modules_count"]) else 0,
            "letter_grade":   score_to_grade(avg),
            "status_color":   score_to_color(avg),
        })
    return out


def get_course_detail(student_id, course_code):
    enroll = load_sheet("Enrollments")
    mods   = load_sheet("Modules")

    enrollment = enroll[(enroll["student_id"] == student_id) & (enroll["course_code"] == course_code)]
    if enrollment.empty:
        return None

    course_mods = mods[(mods["student_id"] == student_id) & (mods["course_code"] == course_code)]
    if course_mods.empty:
        return None

    module_rows = []
    for _, r in course_mods.iterrows():
        score = float(r["module_score"])
        module_rows.append({
            "module_name":          r["module_name"],
            "module_score":         int(score),
            "attendance_percentage":int(r["attendance_percentage"]),
            "study_hours_per_week": int(r["study_hours_per_week"]),
            "assignment_score":     int(r["assignment_score"]),
            "quiz_score":           int(r["quiz_score"]),
            "letter_grade":         score_to_grade(score),
            "status_color":         score_to_color(score),
        })

    enr = enrollment.iloc[0].to_dict()
    avg_score  = float(course_mods["module_score"].mean())
    avg_att    = float(course_mods["attendance_percentage"].mean())
    avg_assign = float(course_mods["assignment_score"].mean())
    avg_quiz   = float(course_mods["quiz_score"].mean())

    return {
        "enrollment_id":  enr["enrollment_id"],
        "course_code":    enr["course_code"],
        "course_title":   enr["course_title"],
        "credits":        int(enr["credits"]),
        "semester":       enr["semester"],
        "status":         enr["status"],
        "avg_score":      round(avg_score, 1),
        "avg_attendance": round(avg_att, 1),
        "avg_assignment": round(avg_assign, 1),
        "avg_quiz":       round(avg_quiz, 1),
        "letter_grade":   score_to_grade(avg_score),
        "status_color":   score_to_color(avg_score),
        "modules":        module_rows,
        "professor":      get_course_professor(course_code),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SMART REMINDERS (per student, based on weak modules)
# ═══════════════════════════════════════════════════════════════════════════════
# Calendar of upcoming academic events. Each entry is tied to a course_code.
# `due_days` is relative to "today".
REMINDERS_CALENDAR = [
    # Upcoming quizzes / assignments / exams across many courses
    {"type": "Quiz",       "course_code": "CSE-101", "topic": "Python Basics Quiz",          "due_days": 3},
    {"type": "Assignment", "course_code": "CSE-201", "topic": "Data Structures Lab Report",  "due_days": 5},
    {"type": "Exam",       "course_code": "CSE-240", "topic": "DBMS Midterm",                "due_days": 12},
    {"type": "Quiz",       "course_code": "CSE-310", "topic": "Operating Systems Quiz",      "due_days": 4},
    {"type": "Exam",       "course_code": "CSE-350", "topic": "Networks Final",              "due_days": 18},
    {"type": "Assignment", "course_code": "CSE-420", "topic": "ML Model Assignment",         "due_days": 7},

    {"type": "Exam",       "course_code": "MTH-101", "topic": "Algebra Midterm",             "due_days": 5},
    {"type": "Quiz",       "course_code": "MTH-201", "topic": "Derivatives Quiz",            "due_days": 2},
    {"type": "Assignment", "course_code": "MTH-240", "topic": "Linear Algebra PS 3",         "due_days": 8},
    {"type": "Exam",       "course_code": "MTH-310", "topic": "Discrete Math Final",         "due_days": 22},
    {"type": "Quiz",       "course_code": "MTH-350", "topic": "Probability Quiz",            "due_days": 6},
    {"type": "Assignment", "course_code": "MTH-420", "topic": "ODE Problem Set",             "due_days": 10},

    {"type": "Assignment", "course_code": "LLW-101", "topic": "Essay Submission Topic 2",    "due_days": 6},
    {"type": "Exam",       "course_code": "LLW-210", "topic": "Comprehension Test",          "due_days": 8},
    {"type": "Quiz",       "course_code": "LLW-245", "topic": "Creative Writing Quiz",       "due_days": 4},
    {"type": "Quiz",       "course_code": "LLW-450", "topic": "Writing Skills Quiz",         "due_days": 17},

    {"type": "Exam",       "course_code": "BUS-220", "topic": "Financial Accounting Exam",   "due_days": 14},
    {"type": "Assignment", "course_code": "BUS-240", "topic": "Market Research Report",      "due_days": 5},
    {"type": "Quiz",       "course_code": "BUS-310", "topic": "Statistics Quiz",             "due_days": 3},
    {"type": "Exam",       "course_code": "BUS-420", "topic": "Corporate Finance Midterm",   "due_days": 16},

    {"type": "Quiz",       "course_code": "NAT-101", "topic": "Cell Biology Quiz",           "due_days": 4},
    {"type": "Exam",       "course_code": "NAT-210", "topic": "General Chemistry Midterm",   "due_days": 9},
    {"type": "Assignment", "course_code": "NAT-245", "topic": "Mechanics Problem Set",       "due_days": 6},

    {"type": "Assignment", "course_code": "AGR-101", "topic": "Soil Analysis Lab",           "due_days": 5},
    {"type": "Exam",       "course_code": "AGR-340", "topic": "Ag Economics Midterm",        "due_days": 11},

    {"type": "Quiz",       "course_code": "HSW-101", "topic": "Anatomy Quiz",                "due_days": 3},
    {"type": "Exam",       "course_code": "HSW-340", "topic": "Exercise Phys Midterm",       "due_days": 13},

    {"type": "Assignment", "course_code": "COM-210", "topic": "News Article Draft",          "due_days": 4},
    {"type": "Quiz",       "course_code": "COM-360", "topic": "Social Media Quiz",           "due_days": 7},

    {"type": "Exam",       "course_code": "EDU-101", "topic": "Foundations Midterm",         "due_days": 10},
    {"type": "Assignment", "course_code": "EDU-330", "topic": "Lesson Plan Assignment",      "due_days": 5},

    {"type": "Assignment", "course_code": "FPA-101", "topic": "Portfolio Submission",        "due_days": 8},
    {"type": "Quiz",       "course_code": "FPA-210", "topic": "Music Theory Quiz",           "due_days": 4},

    {"type": "Exam",       "course_code": "HSS-210", "topic": "World History Midterm",       "due_days": 12},
    {"type": "Assignment", "course_code": "HSS-320", "topic": "Psychology Paper",            "due_days": 6},

    {"type": "Quiz",       "course_code": "INT-101", "topic": "Global Cultures Quiz",        "due_days": 5},
]

COURSE_TITLE_CACHE = None

def _course_title(code):
    """Cached lookup from course_code → course_title."""
    global COURSE_TITLE_CACHE
    if COURSE_TITLE_CACHE is None:
        df = load_sheet("Courses")
        COURSE_TITLE_CACHE = dict(zip(df["course_code"], df["course_title"]))
    return COURSE_TITLE_CACHE.get(code, code)


def get_reminders_for_student(student_id):
    """Return urgency-flagged reminders for a student, prioritized by their weak courses."""
    enrollments = get_student_enrollments(student_id)
    enrolled_codes = {e["course_code"] for e in enrollments}
    # Weak courses = avg_score < 65 or attendance < 70
    weak_codes = {e["course_code"] for e in enrollments
                  if e["avg_score"] < 65 or e["avg_attendance"] < 70}

    today = datetime.today()
    rems = []
    for r in REMINDERS_CALENDAR:
        if r["course_code"] not in enrolled_codes:
            continue
        is_weak = r["course_code"] in weak_codes
        # Show all weak-course reminders; for non-weak, only show next 10 days
        if not is_weak and r["due_days"] > 10:
            continue
        due_date = today + timedelta(days=r["due_days"])
        if r["due_days"] <= 3:
            urgency = "URGENT"
        elif r["due_days"] <= 7:
            urgency = "SOON"
        else:
            urgency = "UPCOMING"
        rems.append({
            "urgency":      urgency,
            "type":         r["type"],
            "course_code":  r["course_code"],
            "course_title": _course_title(r["course_code"]),
            "topic":        r["topic"],
            "due_date":     due_date.strftime("%A, %d %b %Y"),
            "due_days":     r["due_days"],
            "priority":     is_weak,
        })
    # Priority (weak) reminders first, then by due_days
    rems.sort(key=lambda x: (not x["priority"], x["due_days"]))
    return rems


# ═══════════════════════════════════════════════════════════════════════════════
# FACULTY DATA
# ═══════════════════════════════════════════════════════════════════════════════
def get_faculty_dept_stats(dept_id):
    """Return department dashboard stats for a professor's department."""
    students_df = load_sheet("Students")
    summary_df  = load_sheet("Summary")

    dept_students = students_df[students_df["dept_id"] == dept_id]
    dept_ids = dept_students["student_id"].tolist()
    dept_summary = summary_df[summary_df["student_id"].isin(dept_ids)]

    if dept_summary.empty:
        return {
            "total_students":  0,
            "at_risk_count":   0,
            "high_performers": 0,
            "avg_score":       0.0,
            "avg_attendance":  0.0,
        }

    return {
        "total_students":  int(len(dept_summary)),
        "at_risk_count":   int((dept_summary["at_risk"] == "Yes").sum()),
        "high_performers": int((dept_summary["performance_category"] == "High").sum()),
        "medium_count":    int((dept_summary["performance_category"] == "Medium").sum()),
        "low_count":       int((dept_summary["performance_category"] == "Low").sum()),
        "avg_score":       round(float(dept_summary["avg_score"].mean()), 2),
        "avg_attendance":  round(float(dept_summary["avg_attendance"].mean()), 2),
    }


def get_faculty_students(dept_id, sort="risk"):
    """Return list of students in a department with performance data."""
    students_df = load_sheet("Students")
    summary_df  = load_sheet("Summary")
    dept_students = students_df[students_df["dept_id"] == dept_id]
    merged = dept_students.merge(summary_df, on="student_id", how="left")

    out = []
    for _, r in merged.iterrows():
        out.append({
            "student_id":   r["student_id"],
            "name":         r["name"],
            "email":        r["email"],
            "year":         r["year"],
            "program":      r["program"],
            "avg_score":    round(float(r["avg_score"]), 1) if pd.notna(r["avg_score"]) else 0,
            "avg_attendance": round(float(r["avg_attendance"]), 1) if pd.notna(r["avg_attendance"]) else 0,
            "category":     r["performance_category"] if pd.notna(r["performance_category"]) else "N/A",
            "at_risk":      r["at_risk"] if pd.notna(r["at_risk"]) else "No",
            "status_color": score_to_color(float(r["avg_score"])) if pd.notna(r["avg_score"]) else "medium",
        })

    if sort == "risk":
        out.sort(key=lambda s: (s["at_risk"] != "Yes", s["avg_score"]))
    elif sort == "top":
        out.sort(key=lambda s: -s["avg_score"])
    elif sort == "name":
        out.sort(key=lambda s: s["name"])
    return out


def get_all_students_with_dept(sort="risk"):
    """Campus-wide student list with department names (for admin view)."""
    students_df = load_sheet("Students")
    summary_df  = load_sheet("Summary")
    depts_df    = load_sheet("Departments")

    merged = students_df.merge(summary_df, on="student_id", how="left")
    merged = merged.merge(
        depts_df[["dept_id", "name"]].rename(columns={"name": "dept_name"}),
        on="dept_id", how="left",
    )

    out = []
    for _, r in merged.iterrows():
        out.append({
            "student_id":   r["student_id"],
            "name":         r["name"],
            "email":        r["email"],
            "year":         r["year"],
            "program":      r["program"],
            "dept_id":      r["dept_id"],
            "dept_name":    r["dept_name"] if pd.notna(r["dept_name"]) else r["dept_id"],
            "avg_score":    round(float(r["avg_score"]), 1) if pd.notna(r["avg_score"]) else 0,
            "avg_attendance": round(float(r["avg_attendance"]), 1) if pd.notna(r["avg_attendance"]) else 0,
            "category":     r["performance_category"] if pd.notna(r["performance_category"]) else "N/A",
            "at_risk":      r["at_risk"] if pd.notna(r["at_risk"]) else "No",
            "status_color": score_to_color(float(r["avg_score"])) if pd.notna(r["avg_score"]) else "medium",
        })

    if sort == "risk":
        out.sort(key=lambda s: (s["at_risk"] != "Yes", s["avg_score"]))
    elif sort == "top":
        out.sort(key=lambda s: -s["avg_score"])
    elif sort == "name":
        out.sort(key=lambda s: s["name"])
    return out


def get_faculty_courses(prof_id):
    """Courses this professor teaches, with aggregate class-average per course."""
    assigns  = load_sheet("CourseAssignments")
    courses  = load_sheet("Courses")
    mods     = load_sheet("Modules")

    my_assigns = assigns[assigns["prof_id"] == prof_id]
    my_courses = my_assigns.merge(courses, on="course_code", how="left")

    out = []
    for _, r in my_courses.iterrows():
        code = r["course_code"]
        cmods = mods[mods["course_code"] == code]
        if cmods.empty:
            avg_score = avg_att = 0
            n_students = 0
        else:
            avg_score = float(cmods["module_score"].mean())
            avg_att   = float(cmods["attendance_percentage"].mean())
            n_students = cmods["student_id"].nunique()
        out.append({
            "course_code":  code,
            "course_title": r["course_title"],
            "credits":      int(r["credits"]),
            "n_students":   int(n_students),
            "avg_score":    round(avg_score, 1),
            "avg_attendance": round(avg_att, 1),
            "status_color": score_to_color(avg_score),
        })
    out.sort(key=lambda c: c["avg_score"])   # weakest first
    return out


def get_course_student_roster(course_code):
    """For a course, return list of enrolled students with their per-course performance."""
    mods     = load_sheet("Modules")
    students = load_sheet("Students")
    summary  = load_sheet("Summary")

    course_mods = mods[mods["course_code"] == course_code]
    if course_mods.empty:
        return []

    # Aggregate per student
    agg = course_mods.groupby("student_id").agg(
        avg_score      = ("module_score",         "mean"),
        avg_attendance = ("attendance_percentage","mean"),
        avg_assignment = ("assignment_score",     "mean"),
        avg_quiz       = ("quiz_score",           "mean"),
        modules_count  = ("module_score",         "count"),
    ).reset_index()

    merged = agg.merge(students, on="student_id", how="left")
    merged = merged.merge(summary[["student_id", "at_risk"]], on="student_id", how="left")

    out = []
    for _, r in merged.iterrows():
        score = float(r["avg_score"])
        out.append({
            "student_id":     r["student_id"],
            "name":           r["name"],
            "email":          r["email"],
            "year":           r["year"],
            "program":        r["program"],
            "avg_score":      round(score, 1),
            "avg_attendance": round(float(r["avg_attendance"]), 1),
            "avg_assignment": round(float(r["avg_assignment"]), 1),
            "avg_quiz":       round(float(r["avg_quiz"]), 1),
            "modules_count":  int(r["modules_count"]),
            "letter_grade":   score_to_grade(score),
            "status_color":   score_to_color(score),
            "at_risk":        r["at_risk"] if pd.notna(r["at_risk"]) else "No",
        })
    out.sort(key=lambda s: s["avg_score"])   # weakest first
    return out


def get_course_info(course_code):
    """Return metadata for a course: title, credits, modules, dept."""
    courses = load_sheet("Courses")
    row = courses[courses["course_code"] == course_code]
    if row.empty:
        return None
    r = row.iloc[0].to_dict()
    return {
        "course_code":  r["course_code"],
        "course_title": r["course_title"],
        "dept_id":      r["dept_id"],
        "credits":      int(r["credits"]),
        "modules":      [r["module_1"], r["module_2"], r["module_3"]],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN DATA
# ═══════════════════════════════════════════════════════════════════════════════
def get_admin_stats():
    students_df = load_sheet("Students")
    summary_df  = load_sheet("Summary")
    mods_df     = load_sheet("Modules")

    total = len(summary_df)
    return {
        "total_students":  total,
        "at_risk_count":   int((summary_df["at_risk"] == "Yes").sum()),
        "high_performers": int((summary_df["performance_category"] == "High").sum()),
        "medium_count":    int((summary_df["performance_category"] == "Medium").sum()),
        "low_count":       int((summary_df["performance_category"] == "Low").sum()),
        "avg_score":       round(float(summary_df["avg_score"].mean()), 2),
        "avg_attendance":  round(float(summary_df["avg_attendance"].mean()), 2),
        "total_courses":   int(load_sheet("Courses").shape[0]),
        "total_professors":int(load_sheet("Professors").shape[0]),
        "total_departments": int(load_sheet("Departments").shape[0]),
    }


def get_admin_department_breakdown():
    """Per-department rollup."""
    depts = load_sheet("Departments")
    students_df = load_sheet("Students")
    summary_df  = load_sheet("Summary")

    merged = students_df.merge(summary_df, on="student_id", how="left")
    out = []
    for _, d in depts.iterrows():
        dept_id = d["dept_id"]
        rows = merged[merged["dept_id"] == dept_id]
        if rows.empty:
            out.append({**d.to_dict(),
                        "n_students": 0, "avg_score": 0, "avg_attendance": 0,
                        "at_risk": 0, "high_count": 0, "low_count": 0})
            continue
        out.append({
            "dept_id":        dept_id,
            "name":           d["name"],
            "code":           d["code"],
            "school":         d["school"],
            "n_students":     int(len(rows)),
            "avg_score":      round(float(rows["avg_score"].mean()), 1),
            "avg_attendance": round(float(rows["avg_attendance"].mean()), 1),
            "at_risk":        int((rows["at_risk"] == "Yes").sum()),
            "high_count":     int((rows["performance_category"] == "High").sum()),
            "low_count":      int((rows["performance_category"] == "Low").sum()),
        })
    out.sort(key=lambda x: -x["avg_score"])
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════
def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return deco


def _login_as_student(sid, pwd):
    df = load_sheet("StudentCredentials")
    m  = df[(df["student_id"] == sid) & (df["password"] == pwd)]
    if m.empty:
        return False
    session["role"]     = "student"
    session["user_id"]  = sid
    session["name"]     = m.iloc[0]["name"]
    return True


def _login_as_faculty(pid, pwd):
    df = load_sheet("FacultyCredentials")
    m  = df[(df["prof_id"] == pid) & (df["password"] == pwd)]
    if m.empty:
        return False
    session["role"]     = "faculty"
    session["user_id"]  = pid
    session["name"]     = m.iloc[0]["name"]
    session["dept_id"]  = m.iloc[0]["dept_id"]
    return True


def _login_as_admin(aid, pwd):
    df = load_sheet("Admin")
    m  = df[(df["admin_id"] == aid) & (df["password"] == pwd)]
    if m.empty:
        return False
    session["role"]     = "admin"
    session["user_id"]  = aid
    session["name"]     = m.iloc[0]["name"]
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — AUTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def root():
    r = session.get("role")
    if r == "student":  return redirect(url_for("student_dashboard"))
    if r == "faculty":  return redirect(url_for("faculty_dashboard"))
    if r == "admin":    return redirect(url_for("admin_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role   = request.form.get("role", "student").lower()
        userid = request.form.get("user_id", "").strip().upper()
        pwd    = request.form.get("password", "").strip()

        ok = False
        if role == "student":  ok = _login_as_student(userid, pwd)
        elif role == "faculty": ok = _login_as_faculty(userid, pwd)
        elif role == "admin":   ok = _login_as_admin(userid, pwd)

        if not ok:
            flash("Invalid credentials for that role.", "error")
            return render_template("login.html", selected_role=role)

        return redirect(url_for("root"))

    return render_template("login.html", selected_role="student")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — STUDENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    sid     = session["user_id"]
    student = get_student(sid)
    dept    = get_department(student["dept_id"])
    courses = get_student_enrollments(sid)

    if courses:
        overall_avg   = round(sum(c["avg_score"] for c in courses) / len(courses), 1)
        overall_att   = round(sum(c["avg_attendance"] for c in courses) / len(courses), 1)
        total_credits = sum(c["credits"] for c in courses)
    else:
        overall_avg = overall_att = 0
        total_credits = 0

    reminders = get_reminders_for_student(sid)[:6]   # top 6 on dashboard

    return render_template(
        "student_dashboard.html",
        student=student,
        dept=dept,
        courses=courses,
        overall_avg=overall_avg,
        overall_att=overall_att,
        total_credits=total_credits,
        reminders=reminders,
    )


@app.route("/student/course/<course_code>")
@role_required("student")
def student_course(course_code):
    sid    = session["user_id"]
    course = get_course_detail(sid, course_code.upper())
    if course is None:
        flash(f"You are not enrolled in {course_code}.", "error")
        return redirect(url_for("student_dashboard"))
    student = get_student(sid)
    dept    = get_department(student["dept_id"])
    return render_template("student_course.html", student=student, dept=dept, course=course)


@app.route("/student/chat")
@role_required("student")
def student_chat():
    sid       = session["user_id"]
    student   = get_student(sid)
    reminders = get_reminders_for_student(sid)[:6]
    return render_template("chat.html", student=student, reminders=reminders)


@app.route("/student/reminders")
@role_required("student")
def student_reminders():
    sid       = session["user_id"]
    student   = get_student(sid)
    dept      = get_department(student["dept_id"])
    reminders = get_reminders_for_student(sid)   # all
    # Group by urgency
    grouped = {"URGENT": [], "SOON": [], "UPCOMING": []}
    for r in reminders:
        grouped.setdefault(r["urgency"], []).append(r)
    return render_template(
        "student_reminders.html",
        student=student, dept=dept,
        reminders=reminders, grouped=grouped,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — FACULTY
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/faculty/dashboard")
@role_required("faculty")
def faculty_dashboard():
    pid      = session["user_id"]
    prof     = get_professor(pid)
    dept     = get_department(prof["dept_id"])
    stats    = get_faculty_dept_stats(prof["dept_id"])
    students = get_faculty_students(prof["dept_id"], sort="risk")
    courses  = get_faculty_courses(pid)
    return render_template(
        "faculty_dashboard.html",
        prof=prof, dept=dept, stats=stats, students=students, courses=courses,
    )


@app.route("/faculty/student/<student_id>")
@role_required("faculty")
def faculty_student_detail(student_id):
    sid     = student_id.upper()
    student = get_student(sid)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("faculty_dashboard"))

    # Security: faculty can only view students in their own department
    prof = get_professor(session["user_id"])
    if student["dept_id"] != prof["dept_id"]:
        flash("You don't have access to students outside your department.", "error")
        return redirect(url_for("faculty_dashboard"))

    dept    = get_department(student["dept_id"])
    courses = get_student_enrollments(sid)
    summary = load_sheet("Summary")
    s       = summary[summary["student_id"] == sid]
    s_data  = s.iloc[0].to_dict() if not s.empty else {}

    return render_template(
        "faculty_student_detail.html",
        prof=prof, dept=dept, student=student, courses=courses, summary=s_data,
    )


@app.route("/faculty/course/<course_code>")
@role_required("faculty")
def faculty_course_detail(course_code):
    code = course_code.upper()
    info = get_course_info(code)
    if not info:
        flash(f"Course {course_code} not found.", "error")
        return redirect(url_for("faculty_dashboard"))

    # Security: faculty can only view courses they teach
    assigns = load_sheet("CourseAssignments")
    mine = assigns[(assigns["course_code"] == code) & (assigns["prof_id"] == session["user_id"])]
    if mine.empty:
        flash("You do not teach this course.", "error")
        return redirect(url_for("faculty_dashboard"))

    prof    = get_professor(session["user_id"])
    dept    = get_department(prof["dept_id"])
    roster  = get_course_student_roster(code)

    # Class-wide stats
    if roster:
        class_avg_score = round(sum(s["avg_score"] for s in roster) / len(roster), 1)
        class_avg_att   = round(sum(s["avg_attendance"] for s in roster) / len(roster), 1)
        high_count      = sum(1 for s in roster if s["avg_score"] >= 75)
        low_count       = sum(1 for s in roster if s["avg_score"] < 60)
    else:
        class_avg_score = class_avg_att = 0
        high_count = low_count = 0

    return render_template(
        "faculty_course_detail.html",
        prof=prof, dept=dept, course=info, roster=roster,
        class_avg_score=class_avg_score, class_avg_att=class_avg_att,
        high_count=high_count, low_count=low_count,
    )


@app.route("/faculty/chat")
@role_required("faculty")
def faculty_chat():
    prof  = get_professor(session["user_id"])
    dept  = get_department(prof["dept_id"])
    stats = get_faculty_dept_stats(prof["dept_id"])
    return render_template("faculty_chat.html", prof=prof, dept=dept, stats=stats)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — ADMIN
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    stats = get_admin_stats()
    depts = get_admin_department_breakdown()
    return render_template("admin_dashboard.html", stats=stats, depts=depts)


@app.route("/admin/department/<dept_id>")
@role_required("admin")
def admin_department(dept_id):
    dept_id = dept_id.upper()
    dept    = get_department(dept_id)
    if not dept:
        flash("Department not found.", "error")
        return redirect(url_for("admin_dashboard"))
    stats    = get_faculty_dept_stats(dept_id)
    students = get_faculty_students(dept_id, sort="risk")
    return render_template(
        "admin_department.html", dept=dept, stats=stats, students=students,
    )


@app.route("/admin/students")
@role_required("admin")
def admin_students():
    """Campus-wide student list with filter query param (?filter=at_risk|high|low|medium|all)."""
    filt = (request.args.get("filter") or "all").lower()
    all_students = get_all_students_with_dept(sort="risk")

    # Apply server-side filter
    if filt == "at_risk":
        students = [s for s in all_students if s["at_risk"] == "Yes"]
    elif filt == "high":
        students = [s for s in all_students if s["category"] == "High"]
    elif filt == "medium":
        students = [s for s in all_students if s["category"] == "Medium"]
    elif filt == "low":
        students = [s for s in all_students if s["category"] == "Low"]
    else:
        students = all_students

    title_map = {
        "at_risk": "At-Risk Students",
        "high":    "High Performers",
        "low":     "Low Performers",
        "medium":  "Medium Performers",
        "all":     "All Students",
    }
    title = title_map.get(filt, "All Students")
    stats = get_admin_stats()

    return render_template(
        "admin_students.html",
        students=students, stats=stats, filter=filt, title=title,
    )


@app.route("/admin/student/<student_id>")
@role_required("admin")
def admin_student_detail(student_id):
    sid     = student_id.upper()
    student = get_student(sid)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin_dashboard"))

    dept    = get_department(student["dept_id"])
    courses = get_student_enrollments(sid)
    summary = load_sheet("Summary")
    s       = summary[summary["student_id"] == sid]
    s_data  = s.iloc[0].to_dict() if not s.empty else {}

    return render_template(
        "admin_student_detail.html",
        dept=dept, student=student, courses=courses, summary=s_data,
    )


@app.route("/admin/chat")
@role_required("admin")
def admin_chat():
    stats = get_admin_stats()
    depts = get_admin_department_breakdown()
    return render_template("admin_chat.html", stats=stats, depts=depts)


# ═══════════════════════════════════════════════════════════════════════════════
# AI CHAT ENDPOINT  (OpenAI — user provides their own API key)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/apikey", methods=["POST"])
@role_required("student", "faculty", "admin")
def save_apikey():
    """Save the user's OpenAI API key into the session."""
    data = request.get_json(silent=True) or {}
    raw = data.get("api_key") or ""

    # Strip EVERYTHING: leading/trailing whitespace, embedded newlines, and tabs.
    # This catches the common copy-paste-with-trailing-newline mistake.
    key = raw.strip().replace("\n", "").replace("\r", "").replace("\t", "").replace(" ", "")

    if not key:
        return jsonify({"ok": False, "error": "Please paste your OpenAI API key."}), 400
    if not key.startswith("sk-"):
        return jsonify({"ok": False, "error": "That doesn't look like a valid OpenAI API key (must start with 'sk-')."}), 400
    if len(key) < 20:
        return jsonify({"ok": False, "error": "That key looks too short. OpenAI keys are typically 48+ characters. Did the paste get cut off?"}), 400

    session["openai_api_key"] = key
    return jsonify({"ok": True, "key_length": len(key), "key_prefix": key[:7] + "…"})


@app.route("/api/apikey/status")
@role_required("student", "faculty", "admin")
def apikey_status():
    key = session.get("openai_api_key", "")
    if not key:
        return jsonify({"has_key": False})
    return jsonify({
        "has_key": True,
        "key_length": len(key),
        "key_preview": f"{key[:7]}…{key[-4:]}" if len(key) > 12 else f"{key[:4]}…",
    })


@app.route("/api/apikey/test", methods=["POST"])
@role_required("student", "faculty", "admin")
def test_apikey():
    """Test the session's API key against OpenAI /v1/models — real live check."""
    api_key = session.get("openai_api_key")
    if not api_key:
        return jsonify({"ok": False, "error": "No key stored."}), 400
    api_key = api_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")

    import httpx
    try:
        r = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        if r.status_code == 200:
            models = [m["id"] for m in r.json().get("data", [])]
            has_target = "gpt-4o-mini" in models
            return jsonify({
                "ok": True,
                "status": r.status_code,
                "model_count": len(models),
                "has_gpt4o_mini": has_target,
                "message": "✓ Key works." if has_target else "Key works but gpt-4o-mini is NOT available to it.",
            })
        elif r.status_code == 401:
            return jsonify({
                "ok": False,
                "status": 401,
                "message": "OpenAI rejected the key (401 Unauthorized). The key is invalid, revoked, or copied incorrectly.",
                "raw": r.json() if "application/json" in r.headers.get("content-type", "") else r.text[:200],
            }), 401
        elif r.status_code == 429:
            return jsonify({
                "ok": False,
                "status": 429,
                "message": "Rate limit / quota exceeded. Key is valid but your account has no credit.",
            }), 429
        else:
            return jsonify({
                "ok": False,
                "status": r.status_code,
                "message": f"OpenAI returned {r.status_code}.",
                "raw": r.text[:300],
            }), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)}"}), 500


def _build_student_system_prompt(sid):
    student  = get_student(sid)
    dept     = get_department(student["dept_id"])
    courses  = get_student_enrollments(sid)
    rems     = get_reminders_for_student(sid)[:8]

    weak  = [c for c in courses if c["avg_score"] < 65 or c["avg_attendance"] < 70]
    good  = [c for c in courses if c["avg_score"] >= 75]

    lines = [
        "You are CampusIQ — a personal academic advisor.",
        "Be warm, specific, and data-driven. Always use the student's real course codes/titles.",
        "",
        f"STUDENT: {student['name']} ({sid})",
        f"DEPARTMENT: {dept['name']}",
        f"PROGRAM: {student['program']} — {student['year']}",
        "",
        "ENROLLED COURSES (with current performance):",
    ]
    for c in courses:
        lines.append(f"  • {c['course_code']} {c['course_title']}: "
                     f"score {c['avg_score']}/100, attendance {c['avg_attendance']}%, grade {c['letter_grade']}")

    if weak:
        lines += ["", "WEAK COURSES (focus here):"]
        for c in weak:
            lines.append(f"  • {c['course_code']} {c['course_title']}: "
                         f"{c['avg_score']}/100, {c['avg_attendance']}%")

    if good:
        lines += ["", "STRONG COURSES (acknowledge):"]
        for c in good:
            lines.append(f"  • {c['course_code']} {c['course_title']}: {c['avg_score']}/100")

    if rems:
        lines += ["", "UPCOMING DEADLINES:"]
        for r in rems:
            lines.append(f"  • [{r['urgency']}] {r['type']}: {r['topic']} ({r['course_code']}) — "
                         f"{r['due_date']}, {r['due_days']}d away")

    lines += [
        "",
        "GUIDELINES:",
        "  - When giving a study plan, format as Day | Course | Task | Hours.",
        "  - When identifying weak areas, be honest and constructive; name exact modules.",
        "  - Recommend campus resources:",
        "      Math → Math Tutoring Lab (Colden 101, Mon–Fri 9am–5pm)",
        "      CS   → CS Lab (Wells 205, Mon–Thu 10am–6pm)",
        "      Writing → Writing Center (Valk 115, Tue/Thu 2pm–6pm)",
        "      General → Library, 24/7, Owens Library",
        "  - End most responses with 3 clear next steps.",
    ]
    return "\n".join(lines)


@app.route("/api/chat", methods=["POST"])
@role_required("student", "faculty", "admin")
def api_chat():
    """
    AI chat endpoint — calls the published OpenAI Agent Builder workflow.

    Workflow ID: wf_69e6aec4a5b88190a7c7fe6055e25ef701b2fdc8035aa62b
    (from Agent Builder → Code tab)

    The workflow contains:
      [Guardrails] → [Academic Advisor Agent] → [Classify]
        → [Student Advisor] / [Faculty Assistant] / [Admin Analytics]

    We inject real CampusIQ data (from Excel) into the message so the
    agents have full context without needing a file search tool.
    """
    data     = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message."}), 400

    api_key = session.get("openai_api_key")
    if not api_key:
        return jsonify({"error": "no_key"}), 401
    api_key = api_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")

    # ── Your published Agent Builder workflow ID ──────────────────────────────
    WORKFLOW_ID = "wf_69ecec8417a4819097cc54171e65dcae034b80297b5f77e9"

    # ── Build rich context from real Excel data ───────────────────────────────
    role = session["role"]
    if role == "student":
        context = _build_student_context_for_agent(session["user_id"])
    elif role == "faculty":
        context = _build_faculty_context_for_agent(session["user_id"])
    else:
        context = _build_admin_context_for_agent()

    # ── Compose the input for the Agent Builder workflow ─────────────────────
    # The agent has the full dataset uploaded as a File Search tool,
    # so we just tell it WHO is asking and WHAT they want.
    # The agent looks up the student/faculty data itself from the dataset.
    if role == "student":
        student  = get_student(session["user_id"])
        sid      = session["user_id"]
        name     = student["name"]
        full_input = (
            f"ROLE: STUDENT\n"
            f"STUDENT ID: {sid}\n"
            f"STUDENT NAME: {name}\n"
            f"FIRST NAME: {name.split()[0]}\n\n"
            f"PERSONALITY RULES (follow strictly):\n"
            f"- ALWAYS greet by first name: e.g. 'Absolutely {name.split()[0]}!' "
            f"or 'Great question, {name.split()[0]}!'\n"
            f"- Be warm, friendly and encouraging throughout\n"
            f"- Use their first name at least twice in the response\n"
            f"- End with an encouraging sentence using their name\n\n"
            f"USER REQUEST: {user_msg}\n\n"
            f"INSTRUCTION: Search the student dataset for student ID {sid} "
            f"to get their full course data, scores, attendance, and deadlines "
            f"before answering."
        )
    elif role == "faculty":
        prof  = get_professor(session["user_id"])
        pid   = session["user_id"]
        pname = prof["name"]
        full_input = (
            f"ROLE: FACULTY\n"
            f"PROFESSOR ID: {pid}\n"
            f"PROFESSOR NAME: {pname}\n"
            f"DEPARTMENT: {get_department(prof['dept_id'])['name']}\n\n"
            f"PERSONALITY RULES:\n"
            f"- Start with a professional greeting using their name\n"
            f"- Be professional, data-driven, and specific\n\n"
            f"USER REQUEST: {user_msg}\n\n"
            f"INSTRUCTION: Search the faculty dataset for professor ID {pid} "
            f"to get their department stats, courses, and student roster."
        )
    else:
        full_input = (
            f"ROLE: ADMIN\n\n"
            f"PERSONALITY RULES:\n"
            f"- Start with a confident executive-level opening\n"
            f"- Use headings, tables, and specific numbers\n\n"
            f"USER REQUEST: {user_msg}\n\n"
            f"INSTRUCTION: Search the campus dataset to get full campus-wide "
            f"analytics across all departments before answering."
        )

    try:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/workflows/runs",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "OpenAI-Beta":   "workflowsapi_beta=v1",
            },
            json={
                "workflow_id": WORKFLOW_ID,
                "input": {
                    "input_as_text": full_input,
                },
            },
            timeout=60.0,
        )

        # ── Handle non-200 from OpenAI ────────────────────────────────────────
        if response.status_code == 401:
            session.pop("openai_api_key", None)
            return jsonify({
                "error":  "bad_key",
                "detail": "Your API key is invalid or has been revoked. Please re-enter it.",
            }), 401

        if response.status_code == 429:
            return jsonify({
                "error":  "quota",
                "detail": "Your OpenAI account has no credit or hit a rate limit. Add billing at https://platform.openai.com/account/billing",
            }), 429

        if response.status_code == 404:
            # Workflow not found — fall back to plain gpt-4o-mini
            if role == "student":
                ctx = _build_student_context_for_agent(session["user_id"])
            elif role == "faculty":
                ctx = _build_faculty_context_for_agent(session["user_id"])
            else:
                ctx = _build_admin_context_for_agent()
            return _fallback_chat(api_key, role, ctx, user_msg, data.get("history", []))

        if not response.is_success:
            err = response.json() if "application/json" in response.headers.get("content-type", "") else {}
            return jsonify({
                "error":  "api_error",
                "detail": err.get("error", {}).get("message", f"HTTP {response.status_code}"),
            }), 500

        # ── Parse the workflow response ───────────────────────────────────────
        result = response.json()

        # The workflow returns output_text from the final agent node
        reply = (
            result.get("output", {}).get("output_text")
            or result.get("output_text")
            or result.get("output")
            or "I received your message but couldn't generate a response. Please try again."
        )

        return jsonify({
            "reply": reply,
            "mode":  "agent_builder",
            "workflow_id": WORKFLOW_ID,
        })

    except Exception as e:
        err_type = type(e).__name__
        err_str  = str(e)

        is_auth_error  = err_type == "AuthenticationError" or "invalid_api_key" in err_str.lower()
        is_quota_error = "insufficient_quota" in err_str.lower() or err_type == "RateLimitError"

        if is_auth_error:
            session.pop("openai_api_key", None)
            return jsonify({
                "error":  "bad_key",
                "detail": "Your API key is invalid. Please re-enter it.",
            }), 401
        if is_quota_error:
            return jsonify({
                "error":  "quota",
                "detail": "Your OpenAI account has no credit. Add billing at https://platform.openai.com/account/billing",
            }), 429

        # Network error or anything else → fall back to plain chat
        if role == "student":
            ctx = _build_student_context_for_agent(session["user_id"])
        elif role == "faculty":
            ctx = _build_faculty_context_for_agent(session["user_id"])
        else:
            ctx = _build_admin_context_for_agent()
        return _fallback_chat(api_key, role, ctx, user_msg, data.get("history", []))


def _fallback_chat(api_key, role, context, user_msg, history):
    """
    Fallback: plain gpt-4o-mini chat completion.
    Used when the Agent Builder workflow is unreachable.
    """
    try:
        from openai import OpenAI
        system_prompt = _build_system_prompt_for_role(role, context)
        client   = OpenAI(api_key=api_key)
        messages = [{"role": "system", "content": system_prompt}]
        for m in (history or [])[-10:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_msg})
        resp  = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content
        return jsonify({"reply": reply, "mode": "fallback", "tokens": resp.usage.total_tokens})
    except Exception as e:
        err_type = type(e).__name__
        err_str  = str(e)
        is_auth  = err_type == "AuthenticationError" or "invalid_api_key" in err_str.lower()
        is_quota = "insufficient_quota" in err_str.lower() or err_type == "RateLimitError"
        is_model = "model_not_found" in err_str.lower() or err_type == "NotFoundError"
        if is_auth:
            session.pop("openai_api_key", None)
            return jsonify({"error": "bad_key", "detail": "API key is invalid."}), 401
        if is_quota:
            return jsonify({"error": "quota", "detail": "No credit on OpenAI account."}), 429
        if is_model:
            return jsonify({"error": "model_access", "detail": "gpt-4o-mini not accessible."}), 403
        return jsonify({"error": "api_error", "detail": f"{err_type}: {err_str}"}), 500


# ── Context builders — build rich text from real Excel data ──────────────────
# These replace the file search tool. The agent receives full student/faculty/
# admin data as plain text injected into the message, so it can answer
# accurately without needing a Vector Store or file upload.

def _build_student_context_for_agent(sid):
    student  = get_student(sid)
    dept     = get_department(student["dept_id"])
    courses  = get_student_enrollments(sid)
    reminders= get_reminders_for_student(sid)[:8]
    summary  = load_sheet("Summary")
    s_row    = summary[summary["student_id"] == sid]
    avg      = round(float(s_row.iloc[0]["avg_score"]), 1)      if not s_row.empty else "N/A"
    att      = round(float(s_row.iloc[0]["avg_attendance"]), 1) if not s_row.empty else "N/A"
    at_risk  = s_row.iloc[0]["at_risk"] if not s_row.empty else "No"

    weak   = [c for c in courses if c["avg_score"] < 70]
    strong = [c for c in courses if c["avg_score"] >= 80]

    lines = [
        "=== STUDENT DATA ===",
        f"Name: {student['name']} | ID: {sid} | Email: {student['email']}",
        f"Department: {dept['name']} | Program: {student['program']} | Year: {student['year']}",
        f"Overall Avg: {avg}/100 | Attendance: {att}% | At Risk: {at_risk}",
        "",
        "ENROLLED COURSES:",
    ]
    for c in courses:
        lines.append(
            f"  {c['course_code']} {c['course_title']}: "
            f"score={c['avg_score']}/100, attendance={c['avg_attendance']}%, "
            f"grade={c['letter_grade']}"
        )
    lines += [
        "",
        f"WEAK (score<70): {', '.join(c['course_code'] for c in weak) or 'None'}",
        f"STRONG (score≥80): {', '.join(c['course_code'] for c in strong) or 'None'}",
        "",
        "UPCOMING DEADLINES:",
    ]
    for r in reminders:
        lines.append(
            f"  [{r['urgency']}] {r['type']}: {r['topic']} | "
            f"{r['course_code']} | due {r['due_date']} ({r['due_days']}d away)"
        )
    return "\n".join(lines)


def _build_faculty_context_for_agent(pid):
    prof     = get_professor(pid)
    dept     = get_department(prof["dept_id"])
    stats    = get_faculty_dept_stats(prof["dept_id"])
    courses  = get_faculty_courses(pid)
    students = get_faculty_students(prof["dept_id"], sort="risk")

    lines = [
        "=== FACULTY DATA ===",
        f"Professor: {prof['name']} | ID: {pid} | Dept: {dept['name']} ({prof['dept_id']})",
        f"Office: {prof['office']} | Hours: {prof['office_hours']}",
        "",
        "DEPARTMENT STATS:",
        f"  Total students: {stats['total_students']} | At-risk: {stats['at_risk_count']}",
        f"  High performers: {stats['high_performers']} | Avg score: {stats['avg_score']}/100",
        f"  Avg attendance: {stats['avg_attendance']}%",
        "",
        "MY COURSES:",
    ]
    for c in courses:
        lines.append(
            f"  {c['course_code']} {c['course_title']}: "
            f"avg={c['avg_score']}/100, att={c['avg_attendance']}%, "
            f"students={c['n_students']}"
        )
    lines += ["", "STUDENT ROSTER (sorted by risk):"]
    for s in students:
        flag = " ⚠ AT-RISK" if s["at_risk"] == "Yes" else ""
        lines.append(
            f"  {s['student_id']} {s['name']} ({s['year']}): "
            f"score={s['avg_score']}/100, att={s['avg_attendance']}%{flag}"
        )
    return "\n".join(lines)


def _build_admin_context_for_agent():
    stats = get_admin_stats()
    depts = get_admin_department_breakdown()

    lines = [
        "=== CAMPUS DATA ===",
        f"Total students: {stats['total_students']} | At-risk: {stats['at_risk_count']}",
        f"High performers: {stats['high_performers']} | Avg score: {stats['avg_score']}/100",
        f"Avg attendance: {stats['avg_attendance']}% | Departments: {stats['total_departments']}",
        f"Total courses: {stats['total_courses']} | Faculty: {stats['total_professors']}",
        "",
        "DEPARTMENT BREAKDOWN:",
    ]
    for d in depts:
        lines.append(
            f"  {d['dept_id']} {d['name']}: avg={d['avg_score']}/100, "
            f"att={d['avg_attendance']}%, at-risk={d['at_risk']}, "
            f"high={d['high_count']}, students={d['n_students']}"
        )
    return "\n".join(lines)


def _build_system_prompt_for_role(role, context):
    """Wraps context in a role-specific system prompt for fallback mode."""
    if role == "student":
        return (
            "You are CampusIQ's Student AI Advisor. Use ONLY the data below. "
            "Be encouraging, structured, and specific. Never invent data.\n\n"
            + context
        )
    elif role == "faculty":
        return (
            "You are CampusIQ's Faculty AI Assistant. Use ONLY the data below. "
            "Only discuss students within this department. Be analytical.\n\n"
            + context
        )
    else:
        return (
            "You are CampusIQ's Admin AI Insights engine. Use ONLY the data below. "
            "Provide executive-level insights with exact numbers.\n\n"
            + context
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
