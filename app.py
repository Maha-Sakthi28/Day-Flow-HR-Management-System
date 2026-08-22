"""
Dayflow HR Management System
=============================
A complete Flask + MySQL HR Management System.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import random
import string
from datetime import datetime, date, time
from functools import wraps

import mysql.connector
from mysql.connector import Error as MySQLError
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------
# App configuration
# ------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "dayflow-hrms-secret-key-change-in-production"

# ------------------------------------------------------------------
# Database configuration
# Change these values to match your local MySQL setup.
# ------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Maha2007",
    "database": "dayflow_hrms",
}


def get_db_connection():
    """
    Returns a new MySQL connection using DB_CONFIG.
    This is the single, reusable way the app connects to MySQL.
    Caller is responsible for closing the connection (or use get_db()).
    """
    return mysql.connector.connect(**DB_CONFIG)


def get_db():
    """
    Returns a connection stored on Flask's application context `g`,
    so the same request reuses one connection instead of opening
    a new one for every query.
    """
    if "db" not in g:
        g.db = get_db_connection()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


# ------------------------------------------------------------------
# Helpers: ID generation
# ------------------------------------------------------------------
def generate_employee_code(cursor):
    """
    Employee code format: EMP + zero-padded sequential number.
    Example: EMP0001, EMP0002 ...
    Guaranteed unique by checking the employees table.
    """
    cursor.execute("SELECT COUNT(*) AS cnt FROM employees")
    count = cursor.fetchone()["cnt"]
    while True:
        count += 1
        code = f"EMP{count:04d}"
        cursor.execute("SELECT id FROM employees WHERE employee_code = %s", (code,))
        if cursor.fetchone() is None:
            return code


def generate_login_id(cursor, first_name, last_name):
    """
    Login ID generation algorithm (documented):
      - Take first letter of first name + first letter of last name (uppercase)
      - Append the current year (YY) and month (MM) as digits
      - Append a 3-digit sequential counter, incremented until unique
    Example: For "John Doe" registered in Feb 2023 -> JD2302001
    This guarantees a consistent, readable, and unique login ID.
    """
    initials = (first_name[:1] + last_name[:1]).upper()
    yymm = datetime.now().strftime("%y%m")
    seq = 1
    while True:
        login_id = f"{initials}{yymm}{seq:03d}"
        cursor.execute("SELECT id FROM users WHERE login_id = %s", (login_id,))
        if cursor.fetchone() is None:
            return login_id
        seq += 1


def generate_temp_password(length=10):
    """Generates a random temporary password for a newly created employee."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


# ------------------------------------------------------------------
# Auth decorators
# ------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("You are not authorized to access that page.", "error")
            return redirect(url_for("employee_dashboard"))
        return f(*args, **kwargs)
    return decorated


def employee_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "employee":
            flash("You are not authorized to access that page.", "error")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("employee_dashboard"))
    return redirect(url_for("login"))


# ------------------------------------------------------------------
# Admin registration
# ------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not login_id or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html")

        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE login_id = %s", (login_id,))
            if cursor.fetchone():
                flash("That Login ID is already taken. Please choose another.", "error")
                cursor.close()
                return render_template("register.html")

            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, 'admin')",
                (login_id, password_hash),
            )
            db.commit()
            cursor.close()
            flash("Admin account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
        except MySQLError as err:
            flash(f"Database error: could not create account. Please try again.", "error")
            app.logger.error(f"Register error: {err}")
            return render_template("register.html")

    return render_template("register.html")


# ------------------------------------------------------------------
# Login / Logout
# ------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")

        if not login_id or not password:
            flash("Please enter both Login ID and password.", "error")
            return render_template("login.html")

        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE login_id = %s", (login_id,))
            user = cursor.fetchone()
            cursor.close()
        except MySQLError as err:
            flash("Database connection error. Please try again later.", "error")
            app.logger.error(f"Login DB error: {err}")
            return render_template("login.html")

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["login_id"] = user["login_id"]
            flash(f"Welcome back, {user['login_id']}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("employee_dashboard"))
        else:
            flash("Invalid Login ID or password.", "error")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ------------------------------------------------------------------
# ADMIN: Dashboard
# ------------------------------------------------------------------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM employees")
    total_employees = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM attendance WHERE attendance_date = %s",
        (date.today(),),
    )
    today_attendance = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM leave_requests WHERE status = 'Pending'"
    )
    pending_timeoff = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM payroll")
    payroll_count = cursor.fetchone()["total"]

    cursor.close()

    return render_template(
        "admin_dashboard.html",
        total_employees=total_employees,
        today_attendance=today_attendance,
        pending_timeoff=pending_timeoff,
        payroll_count=payroll_count,
    )


# ------------------------------------------------------------------
# ADMIN: Employees list
# ------------------------------------------------------------------
@app.route("/admin/employees")
@admin_required
def admin_employees():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT e.id, e.employee_code, e.first_name, e.last_name, e.email,
               e.department, e.designation, e.joining_date
        FROM employees e
        ORDER BY e.id DESC
        """
    )
    employees = cursor.fetchall()
    cursor.close()
    return render_template("admin_employees.html", employees=employees)


# ------------------------------------------------------------------
# ADMIN: Add employee
# ------------------------------------------------------------------
@app.route("/admin/add-employee", methods=["GET", "POST"])
@admin_required
def admin_add_employee():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()
        joining_date = request.form.get("joining_date", "").strip()

        if not first_name or not last_name or not email or not joining_date:
            flash("First name, last name, email, and joining date are required.", "error")
            return render_template("admin_add_employee.html")

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT id FROM employees WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("An employee with that email already exists.", "error")
            cursor.close()
            return render_template("admin_add_employee.html")

        try:
            login_id = generate_login_id(cursor, first_name, last_name)
            temp_password = generate_temp_password()
            password_hash = generate_password_hash(temp_password)

            cursor.execute(
                "INSERT INTO users (login_id, password_hash, role) VALUES (%s, %s, 'employee')",
                (login_id, password_hash),
            )
            db.commit()
            new_user_id = cursor.lastrowid

            employee_code = generate_employee_code(cursor)

            cursor.execute(
                """
                INSERT INTO employees
                    (user_id, employee_code, first_name, last_name, email,
                     phone, department, designation, joining_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    new_user_id, employee_code, first_name, last_name, email,
                    phone, department, designation, joining_date,
                ),
            )
            db.commit()
            cursor.close()

            flash(
                f"Employee created successfully. "
                f"Login ID: {login_id} | Temporary Password: {temp_password} "
                f"(share these with the employee now — they will not be shown again).",
                "success",
            )
            return redirect(url_for("admin_employees"))

        except MySQLError as err:
            db.rollback()
            cursor.close()
            flash("Database error: could not create employee. Please try again.", "error")
            app.logger.error(f"Add employee error: {err}")
            return render_template("admin_add_employee.html")

    return render_template("admin_add_employee.html")


# ------------------------------------------------------------------
# ADMIN: Employee details
# ------------------------------------------------------------------
@app.route("/admin/employee/<int:emp_id>")
@admin_required
def admin_employee_details(emp_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM employees WHERE id = %s", (emp_id,))
    employee = cursor.fetchone()

    if not employee:
        flash("Employee not found.", "error")
        cursor.close()
        return redirect(url_for("admin_employees"))

    user_id = employee["user_id"]

    cursor.execute(
        "SELECT * FROM attendance WHERE user_id = %s ORDER BY attendance_date DESC LIMIT 10",
        (user_id,),
    )
    attendance_records = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM leave_requests WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    )
    leave_records = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM payroll WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    )
    payroll_records = cursor.fetchall()

    cursor.close()

    return render_template(
        "admin_employee_details.html",
        employee=employee,
        attendance_records=attendance_records,
        leave_records=leave_records,
        payroll_records=payroll_records,
    )


# ------------------------------------------------------------------
# ADMIN: Edit employee
# ------------------------------------------------------------------
@app.route("/admin/employee/<int:emp_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_employee(emp_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE id = %s", (emp_id,))
    employee = cursor.fetchone()

    if not employee:
        flash("Employee not found.", "error")
        cursor.close()
        return redirect(url_for("admin_employees"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()
        joining_date = request.form.get("joining_date", "").strip()

        if not first_name or not last_name or not email or not joining_date:
            flash("First name, last name, email, and joining date are required.", "error")
            cursor.close()
            return render_template("admin_add_employee.html", employee=employee, edit_mode=True)

        try:
            cursor.execute(
                """
                UPDATE employees
                SET first_name = %s, last_name = %s, email = %s, phone = %s,
                    department = %s, designation = %s, joining_date = %s
                WHERE id = %s
                """,
                (first_name, last_name, email, phone, department, designation, joining_date, emp_id),
            )
            db.commit()
            cursor.close()
            flash("Employee updated successfully.", "success")
            return redirect(url_for("admin_employee_details", emp_id=emp_id))
        except MySQLError as err:
            db.rollback()
            cursor.close()
            flash("Database error: could not update employee.", "error")
            app.logger.error(f"Edit employee error: {err}")
            return redirect(url_for("admin_employees"))

    cursor.close()
    return render_template("admin_add_employee.html", employee=employee, edit_mode=True)


# ------------------------------------------------------------------
# ADMIN: Delete employee
# ------------------------------------------------------------------
@app.route("/admin/employee/<int:emp_id>/delete", methods=["POST"])
@admin_required
def admin_delete_employee(emp_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE id = %s", (emp_id,))
    employee = cursor.fetchone()

    if not employee:
        flash("Employee not found.", "error")
        cursor.close()
        return redirect(url_for("admin_employees"))

    try:
        # Deleting the linked user cascades to employees/attendance/leave/payroll
        cursor.execute("DELETE FROM users WHERE id = %s", (employee["user_id"],))
        db.commit()
        cursor.close()
        flash("Employee deleted successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not delete employee.", "error")
        app.logger.error(f"Delete employee error: {err}")

    return redirect(url_for("admin_employees"))


# ------------------------------------------------------------------
# ADMIN: Attendance (all employees)
# ------------------------------------------------------------------
@app.route("/admin/attendance")
@admin_required
def admin_attendance():
    filter_date = request.args.get("date", "").strip()
    filter_user = request.args.get("user_id", "").strip()
    filter_status = request.args.get("status", "").strip()

    query = """
        SELECT a.id, a.attendance_date, a.check_in, a.check_out, a.status,
               e.first_name, e.last_name, e.employee_code, a.user_id
        FROM attendance a
        JOIN employees e ON e.user_id = a.user_id
        WHERE 1=1
    """
    params = []

    if filter_date:
        query += " AND a.attendance_date = %s"
        params.append(filter_date)
    if filter_user:
        query += " AND a.user_id = %s"
        params.append(filter_user)
    if filter_status:
        query += " AND a.status = %s"
        params.append(filter_status)

    query += " ORDER BY a.attendance_date DESC, e.first_name ASC"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(query, tuple(params))
    records = cursor.fetchall()

    cursor.execute(
        "SELECT user_id, first_name, last_name FROM employees ORDER BY first_name"
    )
    employees = cursor.fetchall()
    cursor.close()

    return render_template(
        "admin_attendance.html",
        records=records,
        employees=employees,
        filter_date=filter_date,
        filter_user=filter_user,
        filter_status=filter_status,
    )


# ------------------------------------------------------------------
# ADMIN: Time off
# ------------------------------------------------------------------
@app.route("/admin/timeoff")
@admin_required
def admin_timeoff():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT l.*, e.first_name, e.last_name, e.employee_code
        FROM leave_requests l
        JOIN employees e ON e.user_id = l.user_id
        ORDER BY l.status = 'Pending' DESC, l.created_at DESC
        """
    )
    requests_list = cursor.fetchall()
    cursor.close()
    return render_template("admin_timeoff.html", requests_list=requests_list)


@app.route("/admin/timeoff/<int:req_id>/approve", methods=["POST"])
@admin_required
def admin_timeoff_approve(req_id):
    comment = request.form.get("admin_comment", "").strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM leave_requests WHERE id = %s", (req_id,))
    if not cursor.fetchone():
        flash("Leave request not found.", "error")
        cursor.close()
        return redirect(url_for("admin_timeoff"))

    cursor.execute(
        "UPDATE leave_requests SET status = 'Approved', admin_comment = %s WHERE id = %s",
        (comment, req_id),
    )
    db.commit()
    cursor.close()
    flash("Leave request approved.", "success")
    return redirect(url_for("admin_timeoff"))


@app.route("/admin/timeoff/<int:req_id>/reject", methods=["POST"])
@admin_required
def admin_timeoff_reject(req_id):
    comment = request.form.get("admin_comment", "").strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM leave_requests WHERE id = %s", (req_id,))
    if not cursor.fetchone():
        flash("Leave request not found.", "error")
        cursor.close()
        return redirect(url_for("admin_timeoff"))

    cursor.execute(
        "UPDATE leave_requests SET status = 'Rejected', admin_comment = %s WHERE id = %s",
        (comment, req_id),
    )
    db.commit()
    cursor.close()
    flash("Leave request rejected.", "success")
    return redirect(url_for("admin_timeoff"))


# ------------------------------------------------------------------
# ADMIN: Payroll
# ------------------------------------------------------------------
@app.route("/admin/payroll")
@admin_required
def admin_payroll():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT p.*, e.first_name, e.last_name, e.employee_code
        FROM payroll p
        JOIN employees e ON e.user_id = p.user_id
        ORDER BY p.created_at DESC
        """
    )
    payroll_records = cursor.fetchall()

    cursor.execute(
        "SELECT user_id, first_name, last_name FROM employees ORDER BY first_name"
    )
    employees = cursor.fetchall()
    cursor.close()

    return render_template(
        "admin_payroll.html", payroll_records=payroll_records, employees=employees
    )


@app.route("/admin/payroll/add", methods=["POST"])
@admin_required
def admin_payroll_add():
    user_id = request.form.get("user_id", "").strip()
    basic_salary = request.form.get("basic_salary", "0").strip()
    allowances = request.form.get("allowances", "0").strip()
    deductions = request.form.get("deductions", "0").strip()
    salary_month = request.form.get("salary_month", "").strip()

    if not user_id or not salary_month:
        flash("Employee and salary month are required.", "error")
        return redirect(url_for("admin_payroll"))

    try:
        basic_salary = float(basic_salary)
        allowances = float(allowances)
        deductions = float(deductions)
    except ValueError:
        flash("Salary fields must be valid numbers.", "error")
        return redirect(url_for("admin_payroll"))

    net_salary = basic_salary + allowances - deductions

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO payroll
                (user_id, basic_salary, allowances, deductions, net_salary, salary_month)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, basic_salary, allowances, deductions, net_salary, salary_month),
        )
        db.commit()
        cursor.close()
        flash("Payroll record created successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not create payroll record.", "error")
        app.logger.error(f"Add payroll error: {err}")

    return redirect(url_for("admin_payroll"))


@app.route("/admin/payroll/<int:pay_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_payroll_edit(pay_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT p.*, e.first_name, e.last_name
        FROM payroll p JOIN employees e ON e.user_id = p.user_id
        WHERE p.id = %s
        """,
        (pay_id,),
    )
    record = cursor.fetchone()

    if not record:
        flash("Payroll record not found.", "error")
        cursor.close()
        return redirect(url_for("admin_payroll"))

    if request.method == "POST":
        basic_salary = request.form.get("basic_salary", "0").strip()
        allowances = request.form.get("allowances", "0").strip()
        deductions = request.form.get("deductions", "0").strip()
        salary_month = request.form.get("salary_month", "").strip()

        try:
            basic_salary = float(basic_salary)
            allowances = float(allowances)
            deductions = float(deductions)
        except ValueError:
            flash("Salary fields must be valid numbers.", "error")
            cursor.close()
            return redirect(url_for("admin_payroll"))

        net_salary = basic_salary + allowances - deductions

        cursor.execute(
            """
            UPDATE payroll
            SET basic_salary = %s, allowances = %s, deductions = %s,
                net_salary = %s, salary_month = %s
            WHERE id = %s
            """,
            (basic_salary, allowances, deductions, net_salary, salary_month, pay_id),
        )
        db.commit()
        cursor.close()
        flash("Payroll record updated successfully.", "success")
        return redirect(url_for("admin_payroll"))

    cursor.close()
    return render_template("admin_payroll.html", edit_record=record, payroll_records=[], employees=[])


# ------------------------------------------------------------------
# EMPLOYEE: Dashboard
# ------------------------------------------------------------------
@app.route("/employee/dashboard")
@employee_required
def employee_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE user_id = %s", (session["user_id"],))
    employee = cursor.fetchone()
    cursor.close()

    if not employee:
        flash("Employee profile not found. Please contact your administrator.", "error")

    return render_template("employee_dashboard.html", employee=employee)


# ------------------------------------------------------------------
# EMPLOYEE: Profile
# ------------------------------------------------------------------
@app.route("/employee/profile")
@employee_required
def employee_profile():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees WHERE user_id = %s", (session["user_id"],))
    employee = cursor.fetchone()
    cursor.close()

    if not employee:
        flash("Employee profile not found.", "error")
        return redirect(url_for("employee_dashboard"))

    return render_template("employee_profile.html", employee=employee)


@app.route("/employee/profile/edit", methods=["POST"])
@employee_required
def employee_profile_edit():
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()

    if not email:
        flash("Email cannot be empty.", "error")
        return redirect(url_for("employee_profile"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT id FROM employees WHERE email = %s AND user_id != %s",
        (email, session["user_id"]),
    )
    if cursor.fetchone():
        flash("That email is already in use by another employee.", "error")
        cursor.close()
        return redirect(url_for("employee_profile"))

    try:
        cursor.execute(
            "UPDATE employees SET phone = %s, email = %s WHERE user_id = %s",
            (phone, email, session["user_id"]),
        )
        db.commit()
        cursor.close()
        flash("Profile updated successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not update profile.", "error")
        app.logger.error(f"Profile edit error: {err}")

    return redirect(url_for("employee_profile"))


@app.route("/employee/profile/change-password", methods=["POST"])
@employee_required
def employee_change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_new_password", "")

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "error")
        return redirect(url_for("employee_profile"))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "error")
        return redirect(url_for("employee_profile"))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "error")
        return redirect(url_for("employee_profile"))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "error")
        cursor.close()
        return redirect(url_for("employee_profile"))

    try:
        new_hash = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, session["user_id"]),
        )
        db.commit()
        cursor.close()
        flash("Password changed successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not change password.", "error")
        app.logger.error(f"Change password error: {err}")

    return redirect(url_for("employee_profile"))


# ------------------------------------------------------------------
# EMPLOYEE: Attendance
# ------------------------------------------------------------------
@app.route("/employee/attendance")
@employee_required
def employee_attendance():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM attendance WHERE user_id = %s ORDER BY attendance_date DESC",
        (session["user_id"],),
    )
    records = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM attendance WHERE user_id = %s AND attendance_date = %s",
        (session["user_id"], date.today()),
    )
    today_record = cursor.fetchone()
    cursor.close()

    return render_template(
        "employee_attendance.html", records=records, today_record=today_record
    )


@app.route("/employee/attendance/check-in", methods=["POST"])
@employee_required
def employee_check_in():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    today = date.today()
    now_time = datetime.now().time().replace(microsecond=0)

    cursor.execute(
        "SELECT * FROM attendance WHERE user_id = %s AND attendance_date = %s",
        (session["user_id"], today),
    )
    existing = cursor.fetchone()

    if existing:
        flash("You have already checked in today.", "warning")
        cursor.close()
        return redirect(url_for("employee_attendance"))

    try:
        cursor.execute(
            """
            INSERT INTO attendance (user_id, attendance_date, check_in, status)
            VALUES (%s, %s, %s, 'Present')
            """,
            (session["user_id"], today, now_time),
        )
        db.commit()
        cursor.close()
        flash("Checked in successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not check in.", "error")
        app.logger.error(f"Check-in error: {err}")

    return redirect(url_for("employee_attendance"))


@app.route("/employee/attendance/check-out", methods=["POST"])
@employee_required
def employee_check_out():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    today = date.today()
    now_time = datetime.now().time().replace(microsecond=0)

    cursor.execute(
        "SELECT * FROM attendance WHERE user_id = %s AND attendance_date = %s",
        (session["user_id"], today),
    )
    existing = cursor.fetchone()

    if not existing:
        flash("You must check in before you can check out.", "error")
        cursor.close()
        return redirect(url_for("employee_attendance"))

    if existing["check_out"] is not None:
        flash("You have already checked out today.", "warning")
        cursor.close()
        return redirect(url_for("employee_attendance"))

    try:
        cursor.execute(
            "UPDATE attendance SET check_out = %s WHERE id = %s",
            (now_time, existing["id"]),
        )
        db.commit()
        cursor.close()
        flash("Checked out successfully.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not check out.", "error")
        app.logger.error(f"Check-out error: {err}")

    return redirect(url_for("employee_attendance"))


# ------------------------------------------------------------------
# EMPLOYEE: Time off
# ------------------------------------------------------------------
@app.route("/employee/timeoff")
@employee_required
def employee_timeoff():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM leave_requests WHERE user_id = %s ORDER BY created_at DESC",
        (session["user_id"],),
    )
    requests_list = cursor.fetchall()
    cursor.close()
    return render_template("employee_timeoff.html", requests_list=requests_list)


@app.route("/employee/timeoff/request", methods=["POST"])
@employee_required
def employee_timeoff_request():
    leave_type = request.form.get("leave_type", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    reason = request.form.get("reason", "").strip()

    if not leave_type or not start_date or not end_date:
        flash("Leave type, start date, and end date are required.", "error")
        return redirect(url_for("employee_timeoff"))

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format.", "error")
        return redirect(url_for("employee_timeoff"))

    if end_dt < start_dt:
        flash("End date cannot be before start date.", "error")
        return redirect(url_for("employee_timeoff"))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO leave_requests
                (user_id, leave_type, start_date, end_date, reason, status)
            VALUES (%s, %s, %s, %s, %s, 'Pending')
            """,
            (session["user_id"], leave_type, start_date, end_date, reason),
        )
        db.commit()
        cursor.close()
        flash("Time off request submitted.", "success")
    except MySQLError as err:
        db.rollback()
        cursor.close()
        flash("Database error: could not submit request.", "error")
        app.logger.error(f"Timeoff request error: {err}")

    return redirect(url_for("employee_timeoff"))


# ------------------------------------------------------------------
# EMPLOYEE: Payroll
# ------------------------------------------------------------------
@app.route("/employee/payroll")
@employee_required
def employee_payroll():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM payroll WHERE user_id = %s ORDER BY created_at DESC",
        (session["user_id"],),
    )
    payroll_records = cursor.fetchall()
    cursor.close()
    return render_template("employee_payroll.html", payroll_records=payroll_records)


# ------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", content_override="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server error: {e}")
    flash("An unexpected error occurred. Please try again.", "error")
    return redirect(url_for("index"))


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
