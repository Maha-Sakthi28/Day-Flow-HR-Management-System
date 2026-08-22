# Dayflow HR Management System

A complete, fully functional HR Management System built with **Python Flask**, **MySQL**, and vanilla **HTML/CSS/JavaScript**. No demo data, no placeholder buttons — every feature reads from and writes to a real MySQL database.

## Features

- Secure authentication with hashed passwords (Werkzeug) and Flask sessions
- Role-based access control (Admin vs Employee) enforced on every route
- Admin self-registration
- Admin dashboard with live statistics pulled from MySQL (total employees, today's attendance, pending time off, payroll count)
- Full employee management: add, view, edit, delete
- Automatic user-account + unique login ID + temporary password generation when an employee is created
- Attendance: employee check-in / check-out with duplicate and out-of-order prevention; admin view of all attendance with filters (date, employee, status)
- Time off: employees submit requests; admins approve/reject with an optional comment
- Payroll: admins create and edit payroll records; net salary is calculated automatically; employees view their own payroll history
- Flash messages for success/error/warning/info feedback
- Responsive sidebar layout that adapts navigation based on role

## Technology Stack

**Backend:** Python 3, Flask, mysql-connector-python, Werkzeug
**Frontend:** HTML5, CSS3, vanilla JavaScript, Jinja2 templates
**Database:** MySQL

## Folder Structure

```
HR MANAGEMENT/
│
├── app.py                     # Main Flask application (all routes & logic)
├── requirements.txt
├── .gitignore
├── README.md
│
├── database/
│   └── schema.sql             # Full MySQL schema
│
├── templates/                 # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── admin_dashboard.html
│   ├── admin_employees.html
│   ├── admin_add_employee.html
│   ├── admin_employee_details.html
│   ├── admin_attendance.html
│   ├── admin_timeoff.html
│   ├── admin_payroll.html
│   ├── employee_dashboard.html
│   ├── employee_profile.html
│   ├── employee_attendance.html
│   ├── employee_timeoff.html
│   └── employee_payroll.html
│
└── static/
    ├── css/style.css
    └── js/app.js
```

## Database Design Notes

- `users` holds login credentials for both admins and employees (`role` = `admin` or `employee`).
- `employees` holds the extended profile for employee users, linked via `user_id`.
- `attendance`, `leave_requests`, and `payroll` are all linked directly to `users.id` via `user_id` (not `employee_id`), exactly one record style throughout the app.
- Deleting a user cascades and removes their employee profile, attendance, leave requests, and payroll records.

### Login ID generation algorithm (documented)

When an admin adds a new employee, a login ID is generated as:

```
<First initial><Last initial><YYMM><3-digit sequence>
```

Example: an employee named "John Doe" added in February 2026 gets `JD2602001`. The sequence number increments automatically until a unique login ID is found. A random 10-character temporary password is generated alongside it and shown to the admin **once**, immediately after creation — save it or share it with the employee right away, since it is not stored in plain text or shown again.

### Employee code generation

Employee codes follow the format `EMP0001`, `EMP0002`, etc., incrementing sequentially and checked for uniqueness.

## MySQL Setup

1. Make sure MySQL Server is installed and running locally.
2. Log into MySQL and create the database:

```sql
CREATE DATABASE IF NOT EXISTS dayflow_hrms;
```

3. Load the schema (creates all tables):

```bash
mysql -u root -p dayflow_hrms < database/schema.sql
```

   (The schema file also contains `CREATE DATABASE IF NOT EXISTS dayflow_hrms;` at the top, so running it standalone works too.)

4. Open `app.py` and update the `DB_CONFIG` dictionary near the top with your local MySQL credentials:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "MYSQL_PASSWORD",   # <-- change this
    "database": "dayflow_hrms",
}
```

## Installation & Running Locally

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Then open your browser to:

```
http://127.0.0.1:5000
```

## First-Time Use

1. Go to `http://127.0.0.1:5000/register` and create an **Admin** account (Login ID + password).
2. Log in with that admin account.
3. From the Admin Dashboard, go to **Add Employee** and fill in the employee's details.
4. The system automatically creates a linked user account, generates a unique **Login ID** and a **temporary password**, and displays both once in a flash message — copy these and share them with the employee.
5. The employee logs in at `/login` using those generated credentials and lands on their own Employee Dashboard, where they can view/edit their profile, check in/out of attendance, request time off, and view payroll.
6. Back in the admin area, you can review attendance, approve/reject time off requests, and create/edit payroll records for any employee.

## Git Commands

```bash
git init
git add .
git commit -m "Initial commit: Dayflow HR Management System"
git branch -M main
git remote add origin <your-repository-url>
git push -u origin main
```

(`.gitignore` already excludes `venv/`, `__pycache__/`, `.env`, and editor folders — no secrets are committed.)
