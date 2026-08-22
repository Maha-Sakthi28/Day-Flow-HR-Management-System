import os
import mysql.connector

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Maha2007",
        database="dayflow_hrms"
    )

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login_id = request.form["login_id"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (login_id, password, role)
                VALUES (%s, %s, %s)
                """,
                (login_id, password, "admin")
            )

            connection.commit()

            return redirect(url_for("login"))

        except mysql.connector.Error as error:
            return f"Error: {error}"

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("employee_dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/employee/dashboard")
def employee_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "employee":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    return render_template(
        "employee_dashboard.html",
        name=session["full_name"]
    )


@app.route("/admin/dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    return render_template(
        "admin_dashboard.html",
        name=session["full_name"]
    )


@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)