from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Task, PriorityTask, Note, ChecklistNote, PomodoroSession
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///productivity.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "change-this-in-production"

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ── DASHBOARD ─────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        tasks    = Task.query.order_by(Task.created_at.desc()).all()
        # Analytics: total logged focus minutes across all finished sessions
        sessions = PomodoroSession.query.filter_by(_status="done").all()
        total_focus = sum(s.duration_min for s in sessions)
        return render_template("index.html", tasks=tasks, total_focus=total_focus)

    # ── TASK ENGINE ───────────────────────────────────────────────────────
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

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted.", "info")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>")
    def task_detail(task_id):
        task = Task.query.get_or_404(task_id)
        return render_template("task_detail.html", task=task)

    # ── NOTE ENGINE ───────────────────────────────────────────────────────
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

    # ── TIME ENGINE ───────────────────────────────────────────────────────
    @app.route("/tasks/<int:task_id>/pomodoro/start", methods=["POST"])
    def start_pomodoro(task_id):
        task     = Task.query.get_or_404(task_id)
        duration = int(request.form.get("duration", 25))
        session  = PomodoroSession(task=task, duration_min=duration)
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
            flash(f"Pomodoro done! Logged {session.duration_min} min.", "success")
        return redirect(url_for("task_detail", task_id=session.task_id))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
