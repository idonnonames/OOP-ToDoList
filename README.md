# OOP-ToDoList

# 🎯 Productivity Hub

A comprehensive web application designed to help users track tasks, manage study notes, and maintain focus using a built-in Pomodoro timer. Built with Object-Oriented Programming principles for our final project.

## 🛠️ Tech Stack
* **Backend:** Python, Flask
* **Database:** SQLite, Flask-SQLAlchemy
* **Frontend:** HTML, CSS, Bootstrap 5 (Jinja2 Server-Side Rendering)

## 🏗️ Architecture & OOP Design
This project heavily utilizes Object-Oriented Programming:
* **Inheritance:** Base `Task` class extended by `PriorityTask`. Base `Note` class extended by `ChecklistNote`.
* **Composition:** The `User` object directly owns `Tasks` and `Notes`.
* **Encapsulation:** Private states for timer tracking in the `PomodoroSession` class.

---

## 🚀 How to Run the Project Locally

**Step 1:** Open your terminal and pull the latest code:
`git clone https://github.com/idonnonames/OOP-ToDoList.git`
`cd OOP-ToDoList`
`git pull origin main`

**Step 2:** Turn on your virtual environment:
* Windows: `venv\Scripts\activate`
* Mac: `source venv/bin/activate`

**Step 3:** Install the required packages (Flask & SQLAlchemy):
`pip install -r requirements.txt`

**Step 4:** Start the server!
`python app.py`

Once it is running, click the `http://127.0.0.1:5000`
