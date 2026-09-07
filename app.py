from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3, os
from datetime import date

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = os.path.join(os.path.dirname(__file__), "student_management.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        course TEXT,
        semester INTEGER
    );
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        att_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
        UNIQUE(student_id, subject_id, att_date),
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        exam TEXT NOT NULL,
        marks REAL NOT NULL,
        max_marks REAL NOT NULL,
        UNIQUE(student_id, subject_id, exam),
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    """)
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO users(username,password) VALUES(?,?)", ("admin","admin123"))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u=request.form["username"].strip()
        p=request.form["password"]
        conn=get_db()
        user=conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u,p)).fetchone()
        conn.close()
        if user:
            session["user"]=u
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    conn=get_db()
    stats = {
        "students": conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"],
        "subjects": conn.execute("SELECT COUNT(*) c FROM subjects").fetchone()["c"],
        "present": conn.execute("SELECT COUNT(*) c FROM attendance WHERE status='Present'").fetchone()["c"],
        "absent": conn.execute("SELECT COUNT(*) c FROM attendance WHERE status='Absent'").fetchone()["c"],
    }
    recent=conn.execute("""SELECT a.att_date,a.status,s.name student,sub.name subject
                           FROM attendance a JOIN students s ON s.id=a.student_id
                           JOIN subjects sub ON sub.id=a.subject_id
                           ORDER BY a.id DESC LIMIT 8""").fetchall()
    conn.close()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/students")
@login_required
def students():
    q=request.args.get("q","").strip()
    conn=get_db()
    rows=conn.execute("""SELECT * FROM students
                         WHERE name LIKE ? OR roll_no LIKE ? OR course LIKE ?
                         ORDER BY id DESC""",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    conn.close()
    return render_template("students.html", students=rows, q=q)

@app.route("/students/add", methods=["GET","POST"])
@login_required
def add_student():
    if request.method=="POST":
        data=(request.form["roll_no"].strip(),request.form["name"].strip(),
              request.form.get("email","").strip(),request.form.get("phone","").strip(),
              request.form.get("course","").strip(),request.form.get("semester") or None)
        try:
            conn=get_db()
            conn.execute("INSERT INTO students(roll_no,name,email,phone,course,semester) VALUES(?,?,?,?,?,?)",data)
            conn.commit(); conn.close()
            flash("Student added successfully.","success")
            return redirect(url_for("students"))
        except sqlite3.IntegrityError:
            flash("Roll number already exists.","danger")
    return render_template("student_form.html", student=None)

@app.route("/students/edit/<int:id>", methods=["GET","POST"])
@login_required
def edit_student(id):
    conn=get_db()
    student=conn.execute("SELECT * FROM students WHERE id=?",(id,)).fetchone()
    if not student:
        conn.close(); return "Student not found",404
    if request.method=="POST":
        data=(request.form["roll_no"].strip(),request.form["name"].strip(),
              request.form.get("email","").strip(),request.form.get("phone","").strip(),
              request.form.get("course","").strip(),request.form.get("semester") or None,id)
        try:
            conn.execute("""UPDATE students SET roll_no=?,name=?,email=?,phone=?,course=?,semester=? WHERE id=?""",data)
            conn.commit(); conn.close()
            flash("Student updated.","success"); return redirect(url_for("students"))
        except sqlite3.IntegrityError:
            flash("Roll number already exists.","danger")
    conn.close()
    return render_template("student_form.html", student=student)

@app.route("/students/delete/<int:id>", methods=["POST"])
@login_required
def delete_student(id):
    conn=get_db()
    conn.execute("DELETE FROM students WHERE id=?",(id,))
    conn.commit(); conn.close()
    flash("Student deleted.","success")
    return redirect(url_for("students"))

@app.route("/subjects", methods=["GET","POST"])
@login_required
def subjects():
    conn=get_db()
    if request.method=="POST":
        try:
            conn.execute("INSERT INTO subjects(name,code) VALUES(?,?)",(request.form["name"].strip(),request.form["code"].strip().upper()))
            conn.commit(); flash("Subject added.","success")
        except sqlite3.IntegrityError:
            flash("Subject code already exists.","danger")
        conn.close(); return redirect(url_for("subjects"))
    rows=conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    conn.close()
    return render_template("subjects.html",subjects=rows)

@app.route("/subjects/delete/<int:id>", methods=["POST"])
@login_required
def delete_subject(id):
    conn=get_db(); conn.execute("DELETE FROM subjects WHERE id=?",(id,)); conn.commit(); conn.close()
    flash("Subject deleted.","success"); return redirect(url_for("subjects"))

@app.route("/attendance", methods=["GET","POST"])
@login_required
def attendance():
    conn=get_db()
    students=conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    subjects=conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    if request.method=="POST":
        sid=request.form["student_id"]; subid=request.form["subject_id"]
        d=request.form["att_date"]; status=request.form["status"]
        conn.execute("""INSERT INTO attendance(student_id,subject_id,att_date,status)
                        VALUES(?,?,?,?)
                        ON CONFLICT(student_id,subject_id,att_date)
                        DO UPDATE SET status=excluded.status""",(sid,subid,d,status))
        conn.commit()
        flash("Attendance saved.","success")
    records=conn.execute("""SELECT a.*,s.name student,s.roll_no,sub.name subject
                            FROM attendance a JOIN students s ON s.id=a.student_id
                            JOIN subjects sub ON sub.id=a.subject_id
                            ORDER BY a.att_date DESC,a.id DESC LIMIT 100""").fetchall()
    conn.close()
    return render_template("attendance.html",students=students,subjects=subjects,records=records,today=date.today().isoformat())

@app.route("/marks", methods=["GET","POST"])
@login_required
def marks():
    conn=get_db()
    students=conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    subjects=conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    if request.method=="POST":
        conn.execute("""INSERT INTO marks(student_id,subject_id,exam,marks,max_marks)
                        VALUES(?,?,?,?,?)
                        ON CONFLICT(student_id,subject_id,exam)
                        DO UPDATE SET marks=excluded.marks,max_marks=excluded.max_marks""",
                     (request.form["student_id"],request.form["subject_id"],request.form["exam"],
                      float(request.form["marks"]),float(request.form["max_marks"])))
        conn.commit(); flash("Marks saved.","success")
    records=conn.execute("""SELECT m.*,s.name student,s.roll_no,sub.name subject
                            FROM marks m JOIN students s ON s.id=m.student_id
                            JOIN subjects sub ON sub.id=m.subject_id
                            ORDER BY m.id DESC LIMIT 100""").fetchall()
    conn.close()
    return render_template("marks.html",students=students,subjects=subjects,records=records)

@app.route("/reports")
@login_required
def reports():
    conn=get_db()
    students=conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    report=[]
    for st in students:
        total=conn.execute("SELECT COUNT(*) c FROM attendance WHERE student_id=?",(st["id"],)).fetchone()["c"]
        present=conn.execute("SELECT COUNT(*) c FROM attendance WHERE student_id=? AND status='Present'",(st["id"],)).fetchone()["c"]
        pct=round((present/total)*100,2) if total else 0
        avg=conn.execute("""SELECT AVG((marks/max_marks)*100) a FROM marks WHERE student_id=?""",(st["id"],)).fetchone()["a"]
        report.append({"student":st,"total":total,"present":present,"pct":pct,"avg":round(avg,2) if avg else 0})
    conn.close()
    return render_template("reports.html",report=report)

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
