import os
import re
import sqlite3
import smtplib
from email.message import EmailMessage
from flask import Flask, request, session, jsonify, g
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder='../docs', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

DATABASE = os.path.join(os.path.dirname(__file__), 'app.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS unban_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_id TEXT NOT NULL,
            contact TEXT NOT NULL,
            justification TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.commit()


def send_admin_email(subject, body):
    emails = os.environ.get('ADMIN_EMAILS')
    if not emails:
        return
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.environ.get('MAIL_FROM', 'noreply@example.com')
    msg['To'] = emails
    msg.set_content(body)
    server = os.environ.get('SMTP_SERVER', 'localhost')
    try:
        with smtplib.SMTP(server) as s:
            s.send_message(msg)
    except Exception:
        pass


@app.before_request
def before_request():
    init_db()


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or request.form
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400
    db = get_db()
    cur = db.execute('SELECT username, password, role FROM users WHERE username = ?', (username,))
    row = cur.fetchone()
    if row and check_password_hash(row['password'], password):
        session['user'] = row['username']
        session['role'] = row['role']
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/session')
def api_session():
    user = session.get('user')
    role = session.get('role', 'guest')
    if not user:
        role = 'guest'
    return jsonify({'user': user, 'role': role})


@app.route('/api/unban', methods=['POST'])
def api_unban():
    data = request.get_json() or request.form
    steam_id = (data.get('steam_id') or '').strip()
    contact = (data.get('contact') or '').strip()
    justification = (data.get('justification') or '').strip()
    errors = {}
    if not steam_id:
        errors['steam_id'] = 'SteamID required'
    elif not re.match(r'^(STEAM_[0-5]:[01]:\d+|\d{17})$', steam_id):
        errors['steam_id'] = 'Invalid SteamID format'
    if not contact:
        errors['contact'] = 'Contact info required'
    if len(justification) < 10:
        errors['justification'] = 'Justification too short'
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400
    db = get_db()
    db.execute(
        'INSERT INTO unban_requests (steam_id, contact, justification) VALUES (?, ?, ?)',
        (steam_id, contact, justification)
    )
    db.commit()
    send_admin_email('New unban request',
                     f'SteamID: {steam_id}\nContact: {contact}\nJustification: {justification}')
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
