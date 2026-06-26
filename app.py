import os
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Task, PriorityTask, Note, ChecklistNote, PomodoroSession, ProofFile
from datetime import datetime
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///productivity.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "change-this-in-production"
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

    upload_folder = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # DASHBOARD 
    @app.route("/")
    def index():
        tasks    = Task.query.order_by(Task.created_at.desc()).all()
        # Analytics: total logged focus seconds across all finished sessions
        sessions = PomodoroSession.query.filter_by(_status="done").all()
        total_focus_sec = sum(s.duration_sec for s in sessions)
        total_focus = round(total_focus_sec / 60, 1)

        # Serialize task data for the calendar widget (client-side JS)
        tasks_json = json.dumps([{
            "id":      t.id,
            "title":   t.title,
            "is_done": t.is_done,
            "type":    t.task_type,
            # deadline only exists on PriorityTask; use ISO format or null
            "deadline": t.deadline.strftime("%Y-%m-%d") if hasattr(t, "deadline") and t.deadline else None,
            "created":  t.created_at.strftime("%Y-%m-%d") if t.created_at else None,
        } for t in tasks])

        return render_template("index.html", tasks=tasks, total_focus=total_focus, tasks_json=tasks_json)

    # TASK ENGINE 
    @app.route("/tasks/create", methods=["POST"])
    def create_task():
        title      = request.form.get("title", "").strip()
        task_type  = request.form.get("task_type", "basic")
        priority   = request.form.get("priority", "medium")
        deadline_s = request.form.get("deadline", "").strip()

        if not title:
            flash("Task title cannot be empty.", "danger")
            return redirect(url_for("index"))

        if task_type == "priority":
            deadline = None
            if deadline_s:
                try:
                    deadline = datetime.strptime(deadline_s, "%Y-%m-%dT%H:%M")
                except ValueError:
                    pass
            task = PriorityTask(title=title, priority=priority, deadline=deadline)
        else:
            task = Task(title=title)

        db.session.add(task)
        db.session.commit()
        flash(f"Task '{title}' created!", "success")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/complete", methods=["POST"])
    def complete_task(task_id):
        task = Task.query.get_or_404(task_id)
        task.complete()
        db.session.commit()
        flash(f"Task '{task.title}' marked as done.", "success")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/uncomplete", methods=["POST"])
    def uncomplete_task(task_id):
        task = Task.query.get_or_404(task_id)
        task.uncomplete()
        db.session.commit()
        flash(f"Task '{task.title}' marked as active again.", "info")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        # Clean up proof files from disk
        for proof in task.proofs:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], proof.filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted.", "info")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>")
    def task_detail(task_id):
        task = Task.query.get_or_404(task_id)
        return render_template("task_detail.html", task=task)

    # NOTE ENGINE 
    @app.route("/tasks/<int:task_id>/notes/create", methods=["POST"])
    def create_note(task_id):
        task      = Task.query.get_or_404(task_id)
        content   = request.form.get("content", "").strip()
        note_type = request.form.get("note_type", "text")

        if not content:
            flash("Note content cannot be empty.", "danger")
            return redirect(url_for("task_detail", task_id=task_id))

        if note_type == "checklist":
            note = ChecklistNote(content=content, task=task)
        else:
            note = Note(content=content, task=task)

        db.session.add(note)
        db.session.commit()
        flash("Note added.", "success")
        return redirect(url_for("task_detail", task_id=task_id))

    @app.route("/notes/<int:note_id>/toggle/<int:item_index>", methods=["POST"])
    def toggle_checklist(note_id, item_index):
        note = ChecklistNote.query.get_or_404(note_id)
        note.toggle(item_index)
        db.session.commit()
        return redirect(url_for("task_detail", task_id=note.task_id))

    @app.route("/notes/<int:note_id>/delete", methods=["POST"])
    def delete_note(note_id):
        note = Note.query.get_or_404(note_id)
        task_id = note.task_id
        db.session.delete(note)
        db.session.commit()
        flash("Note deleted.", "info")
        return redirect(url_for("task_detail", task_id=task_id))

    # TIME ENGINE
    @app.route("/tasks/<int:task_id>/pomodoro/start", methods=["POST"])
    def start_pomodoro(task_id):
        task        = Task.query.get_or_404(task_id)
        duration_sec = int(request.form.get("duration", 1500))  # default 25 min in seconds
        session     = PomodoroSession(task=task, duration_sec=duration_sec)
        session.start()
        db.session.add(session)
        db.session.commit()
        return redirect(url_for("pomodoro_view", session_id=session.id))

    @app.route("/pomodoro/<int:session_id>")
    def pomodoro_view(session_id):
        session = PomodoroSession.query.get_or_404(session_id)
        return render_template("pomodoro.html", session=session)

    @app.route("/pomodoro/<int:session_id>/finish", methods=["POST"])
    def finish_pomodoro(session_id):
        session = PomodoroSession.query.get_or_404(session_id)
        if session.status == "running":
            session.finish()
            db.session.commit()
            flash(f"Pomodoro done! Logged {session.format_duration()}.", "success")
        return redirect(url_for("task_detail", task_id=session.task_id))

    # PROOF ENGINE 
    @app.route("/tasks/<int:task_id>/upload", methods=["POST"])
    def upload_proof(task_id):
        task = Task.query.get_or_404(task_id)

        if "proof_file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("task_detail", task_id=task_id))

        file = request.files["proof_file"]
        if file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("task_detail", task_id=task_id))

        if not allowed_file(file.filename):
            flash("File type not allowed. Use images or PDF.", "danger")
            return redirect(url_for("task_detail", task_id=task_id))

        # Save with UUID filename to avoid collisions
        original = secure_filename(file.filename)
        ext = original.rsplit('.', 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))

        proof = ProofFile(
            task=task,
            filename=stored_name,
            original_name=original,
        )
        db.session.add(proof)
        db.session.commit()
        flash(f"Proof '{original}' uploaded.", "success")
        return redirect(url_for("task_detail", task_id=task_id))

    @app.route("/proofs/<int:proof_id>/delete", methods=["POST"])
    def delete_proof(proof_id):
        proof = ProofFile.query.get_or_404(proof_id)
        task_id = proof.task_id
        # Remove file from disk
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], proof.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(proof)
        db.session.commit()
        flash("Proof deleted.", "info")
        return redirect(url_for("task_detail", task_id=task_id))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)