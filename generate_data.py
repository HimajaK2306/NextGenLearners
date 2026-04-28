"""
CampusIQ — Data generation script
Generates: departments, course catalog, student roster (with names/department),
           enrollments, and module-level grades/attendance.

Run this ONCE (or again any time you want fresh data):
    python generate_data.py

Outputs:
    data/campus_data.xlsx   — all sheets (Departments, Courses, Students,
                              Enrollments, Modules, Credentials)
"""
import os
import random
import pandas as pd
from datetime import datetime

random.seed(42)   # reproducible fake data

OUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'campus_data.xlsx')

# ─────────────────────────────────────────────────────────────────────────────
# 1. DEPARTMENTS
# ─────────────────────────────────────────────────────────────────────────────
DEPARTMENTS = [
    {"dept_id": "AGR", "name": "School of Agricultural Sciences",              "code": "03",  "school": "Professional Schools"},
    {"dept_id": "BUS", "name": "Booth School of Business",                      "code": "BUS", "school": "Professional Schools"},
    {"dept_id": "COM", "name": "School of Communication and Mass Media",        "code": "COM", "school": "Professional Schools"},
    {"dept_id": "CSE", "name": "School of Computer Science and Information Systems", "code": "44", "school": "Professional Schools"},
    {"dept_id": "EDU", "name": "School of Education",                           "code": "EDU", "school": "Professional Schools"},
    {"dept_id": "HSW", "name": "School of Health Science and Wellness",         "code": "HSW", "school": "Professional Schools"},
    {"dept_id": "FPA", "name": "Fine and Performing Arts Department",           "code": "FPA", "school": "College of Arts and Sciences"},
    {"dept_id": "HSS", "name": "Humanities and Social Sciences Department",     "code": "HSS", "school": "College of Arts and Sciences"},
    {"dept_id": "INT", "name": "International Study",                           "code": "80",  "school": "College of Arts and Sciences"},
    {"dept_id": "LLW", "name": "Language, Literature, and Writing Department",  "code": "LLW", "school": "College of Arts and Sciences"},
    {"dept_id": "MTH", "name": "Mathematics and Statistics Department",         "code": "17",  "school": "College of Arts and Sciences"},
    {"dept_id": "NAT", "name": "Natural Sciences Department",                   "code": "NAT", "school": "College of Arts and Sciences"},
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. COURSES PER DEPARTMENT  (5-6 each, with 3 modules each)
# ─────────────────────────────────────────────────────────────────────────────
# Format: {dept_id: [ (course_code, course_title, credits, [module1, module2, module3]) ]}
COURSE_CATALOG = {
    "AGR": [
        ("AGR-101", "Introduction to Agronomy",         3, ["Soil Science", "Crop Production", "Plant Nutrition"]),
        ("AGR-210", "Animal Husbandry",                 3, ["Livestock Management", "Dairy Science", "Poultry Science"]),
        ("AGR-225", "Sustainable Farming Systems",      3, ["Organic Methods", "Crop Rotation", "Integrated Pest Mgmt"]),
        ("AGR-340", "Agricultural Economics",           3, ["Farm Finance", "Market Analysis", "Policy & Trade"]),
        ("AGR-410", "Precision Agriculture Technology", 3, ["GPS & GIS", "Remote Sensing", "Data Analytics"]),
        ("AGR-450", "Food Science & Safety",            3, ["Food Microbiology", "Food Processing", "Quality Assurance"]),
    ],
    "BUS": [
        ("BUS-101", "Principles of Management",         3, ["Planning & Strategy", "Organizing", "Leadership"]),
        ("BUS-220", "Financial Accounting",             3, ["Journals & Ledgers", "Financial Statements", "Analysis"]),
        ("BUS-240", "Marketing Fundamentals",           3, ["Consumer Behavior", "Market Research", "Brand Strategy"]),
        ("BUS-310", "Business Statistics",              3, ["Descriptive Stats", "Probability", "Regression"]),
        ("BUS-360", "Operations Management",            3, ["Supply Chain", "Quality Control", "Project Mgmt"]),
        ("BUS-420", "Corporate Finance",                3, ["Capital Budgeting", "Risk & Return", "Valuation"]),
    ],
    "COM": [
        ("COM-101", "Introduction to Mass Communication", 3, ["Media History", "Media Theory", "Ethics"]),
        ("COM-210", "Digital Journalism",               3, ["News Writing", "Multimedia Reporting", "Editing"]),
        ("COM-245", "Public Relations",                 3, ["Campaign Design", "Media Relations", "Crisis Comm"]),
        ("COM-320", "Broadcast Production",             3, ["Audio Production", "Video Production", "Live Streaming"]),
        ("COM-360", "Social Media Strategy",            3, ["Content Strategy", "Analytics", "Community Mgmt"]),
    ],
    "CSE": [
        ("CSE-101", "Introduction to Programming",      3, ["Python Basics", "Control Flow", "Functions & OOP"]),
        ("CSE-201", "Data Structures & Algorithms",     4, ["Arrays & Linked Lists", "Trees & Graphs", "Sorting & Searching"]),
        ("CSE-240", "Database Management Systems",      3, ["Relational Model", "SQL & Normalization", "Transactions"]),
        ("CSE-310", "Operating Systems",                3, ["Processes & Threads", "Memory Management", "File Systems"]),
        ("CSE-350", "Computer Networks",                3, ["OSI & TCP/IP", "Routing Protocols", "Network Security"]),
        ("CSE-420", "Machine Learning",                 4, ["Supervised Learning", "Unsupervised Learning", "Neural Networks"]),
    ],
    "EDU": [
        ("EDU-101", "Foundations of Education",         3, ["History of Ed", "Philosophy", "Ed Policy"]),
        ("EDU-210", "Child Development & Psychology",   3, ["Cognitive Dev", "Social-Emotional", "Learning Theories"]),
        ("EDU-245", "Classroom Management",             3, ["Behavior Strategies", "Engagement", "Inclusion"]),
        ("EDU-330", "Curriculum Design",                3, ["Lesson Planning", "Assessment", "Differentiation"]),
        ("EDU-410", "Teaching with Technology",         3, ["EdTech Tools", "Online Learning", "Digital Literacy"]),
    ],
    "HSW": [
        ("HSW-101", "Human Anatomy & Physiology",       4, ["Cells & Tissues", "Organ Systems I", "Organ Systems II"]),
        ("HSW-210", "Nutrition Science",                3, ["Macronutrients", "Micronutrients", "Dietary Planning"]),
        ("HSW-250", "Community Health",                 3, ["Epidemiology", "Health Promotion", "Global Health"]),
        ("HSW-340", "Exercise Physiology",              3, ["Cardio System", "Muscle Physiology", "Training Principles"]),
        ("HSW-410", "Healthcare Administration",        3, ["Health Policy", "Finance", "Ethics & Law"]),
        ("HSW-450", "Mental Health & Wellness",         3, ["Stress & Coping", "Counseling Intro", "Public Mental Health"]),
    ],
    "FPA": [
        ("FPA-101", "Introduction to Visual Arts",      3, ["Art History", "Drawing Basics", "Color Theory"]),
        ("FPA-210", "Music Theory",                     3, ["Scales & Chords", "Rhythm & Meter", "Harmony"]),
        ("FPA-245", "Theatre & Performance",            3, ["Acting Basics", "Scene Study", "Stagecraft"]),
        ("FPA-320", "Digital Media Art",                3, ["Photoshop", "Illustrator", "Motion Graphics"]),
        ("FPA-410", "Contemporary Art & Design",        3, ["20th Century Art", "Contemporary Movements", "Critique"]),
    ],
    "HSS": [
        ("HSS-101", "Introduction to Sociology",        3, ["Social Structures", "Culture", "Inequality"]),
        ("HSS-210", "World History",                    3, ["Ancient Civilizations", "Middle Ages", "Modern Era"]),
        ("HSS-245", "Political Science",                3, ["Political Theory", "US Government", "Comparative Politics"]),
        ("HSS-320", "Psychology of Behavior",           3, ["Cognition", "Personality", "Social Psychology"]),
        ("HSS-410", "Ethics & Philosophy",              3, ["Ethical Theories", "Applied Ethics", "Logic"]),
        ("HSS-450", "Anthropology",                     3, ["Cultural Anthro", "Physical Anthro", "Fieldwork"]),
    ],
    "INT": [
        ("INT-101", "Global Perspectives",              3, ["World Cultures", "Global Issues", "Cross-Cultural Comm"]),
        ("INT-210", "International Relations",          3, ["Diplomacy", "Global Organizations", "Conflict & Peace"]),
        ("INT-245", "Cultural Studies",                 3, ["Identity", "Globalization", "Media & Culture"]),
        ("INT-320", "Study Abroad Preparation",         3, ["Language Skills", "Travel Logistics", "Cultural Adaptation"]),
        ("INT-410", "Global Economics",                 3, ["Trade Theory", "Dev Economics", "Global Finance"]),
    ],
    "LLW": [
        ("LLW-101", "Composition & Rhetoric",           3, ["Essay Writing", "Argumentation", "Research Writing"]),
        ("LLW-210", "Introduction to Literature",       3, ["Fiction", "Poetry", "Drama"]),
        ("LLW-245", "Creative Writing",                 3, ["Short Fiction", "Poetry Workshop", "Creative Nonfiction"]),
        ("LLW-320", "World Literature",                 3, ["European Lit", "Asian Lit", "Postcolonial Lit"]),
        ("LLW-410", "Linguistics",                      3, ["Phonology", "Syntax", "Sociolinguistics"]),
        ("LLW-450", "Technical Writing",                3, ["Documentation", "Reports", "Editing & Style"]),
    ],
    "MTH": [
        ("MTH-101", "College Algebra",                  3, ["Equations", "Functions", "Polynomials"]),
        ("MTH-201", "Calculus I",                       4, ["Limits", "Derivatives", "Integrals"]),
        ("MTH-240", "Linear Algebra",                   3, ["Matrices", "Vector Spaces", "Eigenvalues"]),
        ("MTH-310", "Discrete Mathematics",             3, ["Logic & Proofs", "Combinatorics", "Graph Theory"]),
        ("MTH-350", "Probability & Statistics",         3, ["Probability", "Distributions", "Inference"]),
        ("MTH-420", "Differential Equations",           3, ["First-Order ODEs", "Higher-Order ODEs", "Systems"]),
    ],
    "NAT": [
        ("NAT-101", "General Biology",                  4, ["Cell Biology", "Genetics", "Ecology"]),
        ("NAT-210", "General Chemistry",                4, ["Atomic Structure", "Bonding", "Stoichiometry"]),
        ("NAT-245", "Physics I: Mechanics",             4, ["Kinematics", "Dynamics", "Energy & Momentum"]),
        ("NAT-320", "Organic Chemistry",                4, ["Functional Groups", "Reactions", "Spectroscopy"]),
        ("NAT-410", "Environmental Science",            3, ["Ecosystems", "Climate", "Sustainability"]),
        ("NAT-450", "Microbiology",                     3, ["Microbial Diversity", "Pathogens", "Lab Techniques"]),
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. FAKE NAMES POOL (realistic, diverse)
# ─────────────────────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Aarav","Aisha","Liam","Emma","Noah","Olivia","Ethan","Sophia","Mason","Ava",
    "Lucas","Isabella","Logan","Mia","James","Amelia","Benjamin","Harper","Elijah","Evelyn",
    "Oliver","Charlotte","Jacob","Luna","William","Aria","Michael","Layla","Alexander","Scarlett",
    "Daniel","Victoria","Henry","Camila","Jackson","Penelope","Sebastian","Nora","Aiden","Riley",
    "Matthew","Zoey","Samuel","Lily","David","Hannah","Joseph","Lillian","Carter","Addison",
    "Owen","Aubrey","Wyatt","Stella","John","Natalie","Jack","Zoe","Luke","Leah",
    "Jayden","Hazel","Dylan","Violet","Grayson","Aurora","Levi","Savannah","Isaac","Audrey",
    "Gabriel","Brooklyn","Julian","Bella","Mateo","Claire","Anthony","Skylar","Jaxon","Lucy",
    "Lincoln","Paisley","Joshua","Everly","Christopher","Anna","Andrew","Caroline","Theodore","Nova",
    "Caleb","Genesis","Ryan","Emilia","Asher","Kennedy","Nathan","Samantha","Thomas","Maya",
    "Leo","Willow","Isaiah","Kinsley","Charles","Naomi","Josiah","Aaliyah","Hudson","Elena",
    "Christian","Sarah","Hunter","Ariana","Connor","Allison","Eli","Gabriella","Ezra","Alice",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
    "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
    "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
    "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
    "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts",
    "Patel","Shah","Kumar","Singh","Khan","Chen","Wang","Kim","Park","Liu",
]

# ─────────────────────────────────────────────────────────────────────────────
# 4. BUILD STUDENTS (120 students, S101–S220)
# ─────────────────────────────────────────────────────────────────────────────
def build_students(n=120):
    students = []
    dept_ids = list(COURSE_CATALOG.keys())
    # Roughly even distribution across departments
    for i in range(n):
        sid = f"S{101 + i}"
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        name  = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{101+i}@campusiq.edu"
        dept  = dept_ids[i % len(dept_ids)]  # round-robin assignment
        year  = random.choice(["Freshman","Sophomore","Junior","Senior"])
        program = {
            "AGR": "B.S. Agricultural Science",
            "BUS": "B.B.A. Business Administration",
            "COM": "B.A. Mass Communication",
            "CSE": "B.S. Computer Science",
            "EDU": "B.S. Education",
            "HSW": "B.S. Health Science",
            "FPA": "B.F.A. Fine Arts",
            "HSS": "B.A. Social Sciences",
            "INT": "B.A. International Studies",
            "LLW": "B.A. English & Writing",
            "MTH": "B.S. Mathematics",
            "NAT": "B.S. Natural Sciences",
        }[dept]
        phone = ""  # intentionally blank — not shown in UI
        students.append({
            "student_id":   sid,
            "name":         name,
            "email":        email,
            "dept_id":      dept,
            "program":      program,
            "year":         year,
            "enrolled_on":  "2024-08-19",   # Fall 2024 semester start
            "password":     sid,             # demo-only: password == student ID
        })
    return students


# ─────────────────────────────────────────────────────────────────────────────
# 5. BUILD ENROLLMENTS + MODULE GRADES
# ─────────────────────────────────────────────────────────────────────────────
def build_enrollments_and_modules(students):
    enrollments = []       # (enrollment_id, student_id, course_code)
    modules     = []       # per-student per-module grade rows

    enroll_counter = 1
    for stu in students:
        dept = stu["dept_id"]
        dept_courses = COURSE_CATALOG[dept]
        # Each student enrolls in 5 courses from their dept (mostly) + 1 elective from another dept
        n_from_dept = min(5, len(dept_courses))
        chosen = random.sample(dept_courses, n_from_dept)

        # Add 1 elective from a random other dept (optional, makes it realistic)
        other_depts = [d for d in COURSE_CATALOG if d != dept]
        elective_dept = random.choice(other_depts)
        elective = random.choice(COURSE_CATALOG[elective_dept])
        chosen_with_elective = chosen + [elective]

        # Student's academic strength profile (randomly skewed)
        base_ability = random.choices(
            ["high","medium","low"], weights=[0.3, 0.5, 0.2]
        )[0]
        base_mean = {"high": 82, "medium": 70, "low": 55}[base_ability]

        for course in chosen_with_elective:
            course_code, course_title, credits, module_list = course
            enrollments.append({
                "enrollment_id": f"E{enroll_counter:05d}",
                "student_id":    stu["student_id"],
                "course_code":   course_code,
                "course_title":  course_title,
                "credits":       credits,
                "semester":      "Fall 2024",
                "status":        "Active",
            })
            enroll_counter += 1

            # Some courses are harder than others for this student (random per-course shift)
            course_diff = random.randint(-10, 8)

            for mod_name in module_list:
                # Score with noise
                score = max(25, min(100, int(random.gauss(base_mean + course_diff, 10))))
                # Attendance correlates with score a bit
                att_mean = max(50, min(98, score + random.randint(-15, 15)))
                attendance = max(40, min(100, int(random.gauss(att_mean, 6))))
                study_hrs = max(1, min(20, int(random.gauss(6 + (score - 60) / 10, 3))))
                assign_score = max(20, min(100, int(random.gauss(score + random.randint(-5,8), 8))))
                quiz_score   = max(20, min(100, int(random.gauss(score + random.randint(-8,8), 8))))

                modules.append({
                    "student_id":            stu["student_id"],
                    "course_code":           course_code,
                    "course_title":          course_title,
                    "module_name":           mod_name,
                    "module_score":          score,
                    "attendance_percentage": attendance,
                    "study_hours_per_week":  study_hrs,
                    "assignment_score":      assign_score,
                    "quiz_score":            quiz_score,
                })
    return enrollments, modules


# ─────────────────────────────────────────────────────────────────────────────
# 6. BUILD SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
def build_summary(modules_df):
    """Per-student overall summary (avg across all modules & courses)."""
    summary = modules_df.groupby("student_id").agg(
        avg_score        = ("module_score",         "mean"),
        avg_attendance   = ("attendance_percentage","mean"),
        modules_count    = ("module_score",         "count"),
    ).reset_index()
    summary["avg_score"]      = summary["avg_score"].round(2)
    summary["avg_attendance"] = summary["avg_attendance"].round(2)

    def categorize(s):
        if s >= 75:  return "High"
        if s >= 60:  return "Medium"
        return "Low"

    summary["performance_category"] = summary["avg_score"].apply(categorize)
    summary["at_risk"] = summary.apply(
        lambda r: "Yes" if (r["avg_score"] < 60 or r["avg_attendance"] < 65) else "No",
        axis=1,
    )
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# 6b. PROFESSORS + COURSE ASSIGNMENTS + ADMIN
# ─────────────────────────────────────────────────────────────────────────────
TITLES = ["Dr.", "Prof.", "Dr.", "Dr.", "Prof."]
OFFICE_BUILDINGS = ["Colden Hall", "Valk Center", "Garrett-Strong", "Wells Hall",
                    "Hughes Fieldhouse", "Martindale Hall", "Owens Library"]

def _office_hours():
    days_opts = [
        "Mon/Wed 10am–12pm",  "Tue/Thu 2pm–4pm",    "Mon/Wed/Fri 9am–10am",
        "Wed 1pm–4pm",        "Tue 10am–12pm, Thu 3pm–5pm",
        "Mon/Thu 11am–1pm",   "By appointment",     "Fri 9am–12pm",
    ]
    return random.choice(days_opts)


def build_professors():
    """3 professors per department = 36 professors total."""
    professors = []
    pid = 1
    for dept in DEPARTMENTS:
        dept_id = dept["dept_id"]
        for _ in range(3):
            first = random.choice(FIRST_NAMES)
            last  = random.choice(LAST_NAMES)
            title = random.choice(TITLES)
            name  = f"{title} {first} {last}"
            email = f"{first.lower()}.{last.lower()}@campusiq.edu"
            prof_id = f"P{pid:03d}"
            professors.append({
                "prof_id":      prof_id,
                "name":         name,
                "email":        email,
                "dept_id":      dept_id,
                "office":       f"Room {random.randint(100,499)}, {random.choice(OFFICE_BUILDINGS)}",
                "office_hours": _office_hours(),
                "password":     prof_id,   # demo: password == prof_id
            })
            pid += 1
    return professors


def build_course_assignments(professors_df):
    """Assign each course to one professor from that course's department."""
    assignments = []
    for dept_id, courses in COURSE_CATALOG.items():
        dept_profs = professors_df[professors_df["dept_id"] == dept_id]["prof_id"].tolist()
        for course_code, _, _, _ in courses:
            assignments.append({
                "course_code": course_code,
                "prof_id":     random.choice(dept_profs),
            })
    return assignments


def build_admin():
    return [{
        "admin_id":  "ADMIN",
        "name":      "Campus Administrator",
        "email":     "admin@campusiq.edu",
        "password":  "admin123",
    }]


# ─────────────────────────────────────────────────────────────────────────────
# 7. WRITE TO EXCEL
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("→ Building departments ...")
    dept_df = pd.DataFrame(DEPARTMENTS)

    print("→ Building course catalog ...")
    course_rows = []
    for dept_id, courses in COURSE_CATALOG.items():
        for code, title, credits, mods in courses:
            course_rows.append({
                "course_code":  code,
                "course_title": title,
                "dept_id":      dept_id,
                "credits":      credits,
                "module_1":     mods[0],
                "module_2":     mods[1],
                "module_3":     mods[2],
            })
    courses_df = pd.DataFrame(course_rows)

    print("→ Building students ...")
    students = build_students(120)
    students_df = pd.DataFrame(students)

    print("→ Building enrollments + module grades ...")
    enrollments, modules = build_enrollments_and_modules(students)
    enrollments_df = pd.DataFrame(enrollments)
    modules_df     = pd.DataFrame(modules)

    print("→ Building summary ...")
    summary_df = build_summary(modules_df)

    print("→ Building professors ...")
    professors  = build_professors()
    profs_df    = pd.DataFrame(professors)

    print("→ Assigning courses to professors ...")
    assigns_df  = pd.DataFrame(build_course_assignments(profs_df))

    print("→ Building admin ...")
    admin_df    = pd.DataFrame(build_admin())

    # Credentials (demo-only) — separate tables for clarity
    student_creds_df = students_df[["student_id","name","email","password"]].copy()
    faculty_creds_df = profs_df[["prof_id","name","email","dept_id","password"]].copy()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as w:
        dept_df.to_excel(w,          sheet_name="Departments",        index=False)
        courses_df.to_excel(w,       sheet_name="Courses",            index=False)
        students_df.to_excel(w,      sheet_name="Students",           index=False)
        enrollments_df.to_excel(w,   sheet_name="Enrollments",        index=False)
        modules_df.to_excel(w,       sheet_name="Modules",            index=False)
        summary_df.to_excel(w,       sheet_name="Summary",            index=False)
        profs_df.to_excel(w,         sheet_name="Professors",         index=False)
        assigns_df.to_excel(w,       sheet_name="CourseAssignments",  index=False)
        admin_df.to_excel(w,         sheet_name="Admin",              index=False)
        student_creds_df.to_excel(w, sheet_name="StudentCredentials", index=False)
        faculty_creds_df.to_excel(w, sheet_name="FacultyCredentials", index=False)

    print(f"\n✓ Done. Wrote {OUT_PATH}")
    print(f"  {len(dept_df)} departments")
    print(f"  {len(courses_df)} courses")
    print(f"  {len(students_df)} students")
    print(f"  {len(enrollments_df)} enrollments")
    print(f"  {len(modules_df)} module-grade rows")
    print(f"  {len(profs_df)} professors")
    print(f"  {len(assigns_df)} course-professor assignments")
    print(f"  1 super-admin (login: ADMIN / admin123)")


if __name__ == "__main__":
    main()
