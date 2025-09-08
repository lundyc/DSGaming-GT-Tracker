import os
import sqlite3
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
    db.commit()


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


if __name__ == '__main__':
    app.run(debug=True)
