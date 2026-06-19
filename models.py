from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ─────────────────────────────────────────────
#  TASK ENGINE  (Inheritance)
# ─────────────────────────────────────────────

class Task(db.Model):
    """Base task class. Stores common fields for every task."""
    __tablename__ = "tasks"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    is_done     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    task_type   = db.Column(db.String(20), default="basic")   # discriminator

    # Composition: a Task HAS many Notes
    notes       = db.relationship("Note", back_populates="task",
                                  cascade="all, delete-orphan")
    # Aggregation: a Task IS LINKED TO many PomodoroSessions
    sessions    = db.relationship("PomodoroSession", back_populates="task",
                                  cascade="all, delete-orphan")
    # Composition: a Task HAS many ProofFiles
    proofs      = db.relationship("ProofFile", back_populates="task",
                                  cascade="all, delete-orphan")

    __mapper_args__ = {
        "polymorphic_on":       task_type,
        "polymorphic_identity": "basic",
    }

    def complete(self):
        self.is_done = True

    def uncomplete(self):
        self.is_done = False

    def __repr__(self):
        return f"<Task id={self.id} title={self.title!r} done={self.is_done}>"


class PriorityTask(Task):
    """
    Subclass of Task that adds a priority level and optional deadline.
    Demonstrates INHERITANCE.
    """
    __tablename__ = "priority_tasks"

    id          = db.Column(db.Integer, db.ForeignKey("tasks.id"), primary_key=True)
    priority    = db.Column(db.String(10), default="medium")   # low / medium / high
    deadline    = db.Column(db.DateTime, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "priority"}

    def is_overdue(self):
        """Returns True if the deadline has passed and task is not done."""
        if self.deadline and not self.is_done:
            return datetime.utcnow() > self.deadline
        return False

    def __repr__(self):
        return (f"<PriorityTask id={self.id} title={self.title!r} "
                f"priority={self.priority} overdue={self.is_overdue()}>")


# ─────────────────────────────────────────────
#  NOTE ENGINE  (Composition + Polymorphism)
# ─────────────────────────────────────────────

class Note(db.Model):
    """
    Base note. Linked to a Task (Composition).
    Subclassed by ChecklistNote (Polymorphism).
    """
    __tablename__ = "notes"

    id          = db.Column(db.Integer, primary_key=True)
    content     = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    note_type   = db.Column(db.String(20), default="text")

    task_id     = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    task        = db.relationship("Task", back_populates="notes")

    __mapper_args__ = {
        "polymorphic_on":       note_type,
        "polymorphic_identity": "text",
    }

    def render(self):
        """Polymorphic render — overridden by subclasses."""
        return self.content

    def __repr__(self):
        return f"<Note id={self.id} task_id={self.task_id}>"


class ChecklistNote(Note):
    """
    Note whose content is a newline-separated checklist.
    Demonstrates POLYMORPHISM — render() behaves differently.
    """
    __tablename__ = "checklist_notes"

    id          = db.Column(db.Integer, db.ForeignKey("notes.id"), primary_key=True)
    # Stores checked item indices as comma-separated string e.g. "0,2"
    checked     = db.Column(db.String(500), default="")

    __mapper_args__ = {"polymorphic_identity": "checklist"}

    def items(self):
        """Returns list of (text, is_checked) tuples."""
        checked_indices = set(
            int(i) for i in self.checked.split(",") if i.strip().isdigit()
        )
        return [
            (line, idx in checked_indices)
            for idx, line in enumerate(self.content.splitlines())
            if line.strip()
        ]

    def toggle(self, index: int):
        """Toggle a checklist item by its index."""
        checked_set = set(
            int(i) for i in self.checked.split(",") if i.strip().isdigit()
        )
        if index in checked_set:
            checked_set.discard(index)
        else:
            checked_set.add(index)
        self.checked = ",".join(str(i) for i in sorted(checked_set))

    def render(self):
        """Returns HTML-friendly checklist representation."""
        lines = []
        for text, is_checked in self.items():
            mark = "[x]" if is_checked else "[ ]"
            lines.append(f"{mark} {text}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<ChecklistNote id={self.id} items={len(self.items())}>"


# ─────────────────────────────────────────────
#  TIME ENGINE  (Encapsulation)
# ─────────────────────────────────────────────

class PomodoroSession(db.Model):
    """
    Logs a completed Pomodoro block.
    Demonstrates ENCAPSULATION: timer state is managed through
    methods, not direct attribute mutation from outside.
    """
    __tablename__ = "pomodoro_sessions"

    id           = db.Column(db.Integer, primary_key=True)
    task_id      = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    duration_sec = db.Column(db.Integer, default=1500)  # stored in seconds (25 min = 1500)
    started_at   = db.Column(db.DateTime, nullable=True)
    ended_at     = db.Column(db.DateTime, nullable=True)

    # Encapsulated timer state — only mutated via methods below
    _status      = db.Column("status", db.String(20), default="idle")

    task         = db.relationship("Task", back_populates="sessions")

    # ── public interface ──────────────────────
    @property
    def status(self):
        return self._status

    @property
    def duration_min(self):
        """Backward-compatible property: returns minutes (rounded)."""
        return round(self.duration_sec / 60, 1)

    def start(self):
        current = self._status or "idle"
        if current != "idle":
            raise ValueError(f"Cannot start a session that is '{current}'.")
        self._status    = "running"
        self.started_at = datetime.utcnow()

    def finish(self):
        if self._status != "running":
            raise ValueError(f"Cannot finish a session that is '{self._status}'.")
        self._status = "done"
        self.ended_at = datetime.utcnow()

    def cancel(self):
        self._status = "cancelled"

    @property
    def actual_minutes(self):
        """Real elapsed minutes (only valid after finish())."""
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return round(delta.total_seconds() / 60, 1)
        return 0

    def format_duration(self):
        """Human-readable duration string."""
        m, s = divmod(self.duration_sec, 60)
        if s == 0:
            return f"{m}m"
        return f"{m}m {s}s"

    def __repr__(self):
        return (f"<PomodoroSession id={self.id} task_id={self.task_id} "
                f"status={self._status} dur={self.duration_sec}s>")


# ─────────────────────────────────────────────
#  PROOF ENGINE  (Composition)
# ─────────────────────────────────────────────

class ProofFile(db.Model):
    """
    Stores a proof-of-completion file uploaded by the user.
    Linked to a Task via Composition.
    """
    __tablename__ = "proof_files"

    id            = db.Column(db.Integer, primary_key=True)
    task_id       = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    filename      = db.Column(db.String(255), nullable=False)   # stored UUID filename
    original_name = db.Column(db.String(255), nullable=False)   # user's original filename
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    task          = db.relationship("Task", back_populates="proofs")

    def is_image(self):
        """Check if the file is an image based on extension."""
        ext = self.original_name.rsplit('.', 1)[-1].lower() if '.' in self.original_name else ''
        return ext in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp')

    def __repr__(self):
        return f"<ProofFile id={self.id} task_id={self.task_id} file={self.original_name!r}>"
