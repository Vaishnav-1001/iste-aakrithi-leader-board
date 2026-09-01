import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from urllib.parse import quote_plus
from datetime import datetime
from flask_login import current_user

load_dotenv()
app = Flask(__name__)

# -------------------------
# Flask Configuration
# -------------------------

# Load values from .env
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

# Flask secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# MySQL configuration
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# -------------------------
# Database
# -------------------------

db = SQLAlchemy(app)

# -------------------------
# Login Manager
# -------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# =========================
# DATABASE MODELS
# =========================

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, default=0)

# =========================
# LOGIN USER
# =========================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

# =========================
# HOME & SCORES
# =========================

@app.route("/")
def home():
    return redirect(url_for("scores"))

@app.route("/scores")
def scores():
    students = Student.query.order_by(Student.student_id).all()
    return render_template("scores.html", students=students)

@app.route("/api/scores")
def get_scores():
    students = Student.query.order_by(Student.student_id).all()
    data = [
        {
            "student_id": student.student_id,
            "name": student.name,
            "score": student.score
        }
        for student in students
    ]
    return jsonify(data)

# =========================
# ADMIN ROUTES
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            login_user(admin)
            return redirect(url_for("admin"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/admin")
@login_required
def admin():
    students = Student.query.order_by(Student.student_id).all()
    return render_template("admin.html", students=students)

@app.route("/admin/update", methods=["POST"])
@login_required
def update_score():
    student_id = request.form["student_id"].strip()
    points = int(request.form["score"])
    task_name = request.form.get("task_name", "General Points").strip()

    student = Student.query.filter_by(student_id=student_id).first()

    if student:
        old_score = student.score
        student.score += points

        # Record history entry
        history_entry = ScoreHistory(
            student_id=student_id,
            admin_username=current_user.username,
            points=points,
            task_name=task_name
        )
        db.session.add(history_entry)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{points} points added successfully!",
            "old_score": old_score,
            "new_score": student.score
        })

    return jsonify({"success": False, "message": "Student not found"})

# =========================
# DELETE SCORE
# =========================

@app.route("/admin/delete-score/<int:history_id>", methods=["POST"])
@login_required
def delete_score(history_id):
    # Find the history record
    history_item = db.session.get(ScoreHistory, history_id)
    if not history_item:
        return jsonify({"success": False, "message": "History record not found"}), 404

    # Find the corresponding student
    student = Student.query.filter_by(student_id=history_item.student_id).first()
    if student:
        # Deduct score and prevent negative total score
        student.score = max(0, student.score - history_item.points)

        # Delete history record
        db.session.delete(history_item)
        db.session.commit()

        return jsonify({
            "success": True, 
            "message": "Score rolled back successfully!"
        })

    return jsonify({"success": False, "message": "Student not found"}), 404



@app.route("/admin/add-student", methods=["POST"])
@login_required
def add_student():
    student_id = request.form["student_id"].strip()
    name = request.form["name"].strip()
    score = request.form["score"]

    existing_student = Student.query.filter_by(student_id=student_id).first()

    if existing_student:
        return jsonify({"success": False, "message": "Student ID already exists"})

    new_student = Student(
        student_id=student_id,
        name=name,
        score=int(score)
    )

    db.session.add(new_student)
    db.session.commit()

    return jsonify({"success": True, "message": "Student added successfully"})


class ScoreHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey("student.student_id"), nullable=False)
    admin_username = db.Column(db.String(50), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    task_name = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)




@app.route("/admin/profile/<student_id>")
@login_required
def profile(student_id):
    student = Student.query.filter_by(student_id=student_id).first()
    if not student:
        return "Student not found", 404

    history = ScoreHistory.query.filter_by(student_id=student_id).order_by(ScoreHistory.timestamp.desc()).all()
    return render_template("profile.html", student=student, history=history)


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# =========================
# INITIALIZATION & RUN
# =========================

with app.app_context():
    db.create_all()

    admins = [
        ("admin1", "admin123"),
        ("admin2", "admin123"),
        ("admin3", "admin123")
    ]

    for username, password in admins:
        existing = Admin.query.filter_by(username=username).first()
        if not existing:
            new_admin = Admin(
                username=username,
                password=generate_password_hash(password)
            )
            db.session.add(new_admin)

    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)