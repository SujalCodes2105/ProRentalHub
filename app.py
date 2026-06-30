from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from database import get_db, init_db
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'prorentalhub_secret_2024'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    db = get_db()
    search = request.args.get('search', '')
    city = request.args.get('city', '')
    ptype = request.args.get('type', '')
    query = "SELECT p.*, u.name as owner_name, u.phone as owner_phone FROM properties p JOIN users u ON p.owner_id = u.id WHERE p.status='approved'"
    params = []
    if search:
        query += " AND (p.title LIKE ? OR p.location LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if city:
        query += " AND p.city LIKE ?"
        params.append(f'%{city}%')
    if ptype:
        query += " AND p.property_type=?"
        params.append(ptype)
    query += " ORDER BY p.created_at DESC"
    properties = db.execute(query, params).fetchall()
    db.close()
    return render_template('index.html', properties=properties, search=search, city=city, ptype=ptype)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        phone = request.form['phone']
        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash('Email already registered!', 'danger')
            db.close()
            return redirect(url_for('register'))
        db.execute("INSERT INTO users (name, email, password, role, phone) VALUES (?,?,?,?,?)",
                   (name, email, password, role, phone))
        db.commit()
        db.close()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        db.close()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_role'] == 'admin':
        return redirect(url_for('admin'))
    db = get_db()
    if session['user_role'] == 'owner':
        properties = db.execute(
            "SELECT * FROM properties WHERE owner_id=? ORDER BY created_at DESC",
            (session['user_id'],)
        ).fetchall()
    else:
        properties = db.execute(
            "SELECT p.*, u.name as owner_name, u.phone as owner_phone FROM properties p JOIN users u ON p.owner_id=u.id WHERE p.status='approved' ORDER BY p.created_at DESC"
        ).fetchall()
    db.close()
    return render_template('dashboard.html', properties=properties)

@app.route('/add_property', methods=['GET', 'POST'])
def add_property():
    if 'user_id' not in session or session['user_role'] != 'owner':
        flash('Only owners can add properties.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        property_type = request.form['property_type']
        price = request.form['price']
        location = request.form['location']
        city = request.form['city']
        bedrooms = request.form.get('bedrooms', 0)
        bathrooms = request.form.get('bathrooms', 0)
        area = request.form.get('area', 0)
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                image_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        db = get_db()
        db.execute('''
            INSERT INTO properties (owner_id, title, description, property_type, price, location, city, bedrooms, bathrooms, area, image_filename, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending')
        ''', (session['user_id'], title, description, property_type, price, location, city, bedrooms, bathrooms, area, image_filename))
        db.commit()
        db.close()
        flash('Property submitted for admin approval!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_property.html')

@app.route('/edit_property/<int:pid>', methods=['GET', 'POST'])
def edit_property(pid):
    if 'user_id' not in session or session['user_role'] != 'owner':
        return redirect(url_for('login'))
    db = get_db()
    prop = db.execute("SELECT * FROM properties WHERE id=? AND owner_id=?", (pid, session['user_id'])).fetchone()
    if not prop:
        flash('Property not found.', 'danger')
        db.close()
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        property_type = request.form['property_type']
        price = request.form['price']
        location = request.form['location']
        city = request.form['city']
        bedrooms = request.form.get('bedrooms', 0)
        bathrooms = request.form.get('bathrooms', 0)
        area = request.form.get('area', 0)
        image_filename = prop['image_filename']
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                image_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        db.execute('''
            UPDATE properties SET title=?, description=?, property_type=?, price=?, location=?, city=?,
            bedrooms=?, bathrooms=?, area=?, image_filename=?, status='pending'
            WHERE id=? AND owner_id=?
        ''', (title, description, property_type, price, location, city, bedrooms, bathrooms, area, image_filename, pid, session['user_id']))
        db.commit()
        db.close()
        flash('Property updated! Awaiting re-approval.', 'success')
        return redirect(url_for('dashboard'))
    db.close()
    return render_template('edit_property.html', prop=prop)

@app.route('/delete_property/<int:pid>')
def delete_property(pid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    db.execute("DELETE FROM properties WHERE id=? AND owner_id=?", (pid, session['user_id']))
    db.commit()
    db.close()
    flash('Property deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/property/<int:pid>')
def property_detail(pid):
    db = get_db()
    prop = db.execute(
        "SELECT p.*, u.name as owner_name, u.phone as owner_phone, u.email as owner_email FROM properties p JOIN users u ON p.owner_id=u.id WHERE p.id=? AND p.status='approved'",
        (pid,)
    ).fetchone()
    db.close()
    if not prop:
        flash('Property not found or not approved yet.', 'danger')
        return redirect(url_for('index'))
    return render_template('property_detail.html', prop=prop)

@app.route('/admin')
def admin():
    if 'user_id' not in session or session['user_role'] != 'admin':
        flash('Admin access only.', 'danger')
        return redirect(url_for('login'))
    db = get_db()
    pending = db.execute(
        "SELECT p.*, u.name as owner_name, u.phone as owner_phone FROM properties p JOIN users u ON p.owner_id=u.id WHERE p.status='pending' ORDER BY p.created_at DESC"
    ).fetchall()
    approved = db.execute(
        "SELECT p.*, u.name as owner_name FROM properties p JOIN users u ON p.owner_id=u.id WHERE p.status='approved' ORDER BY p.created_at DESC"
    ).fetchall()
    rejected = db.execute(
        "SELECT p.*, u.name as owner_name FROM properties p JOIN users u ON p.owner_id=u.id WHERE p.status='rejected' ORDER BY p.created_at DESC"
    ).fetchall()
    users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    db.close()
    return render_template('admin.html', pending=pending, approved=approved, rejected=rejected, users=users)

@app.route('/admin/approve/<int:pid>')
def approve_property(pid):
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    db.execute("UPDATE properties SET status='approved' WHERE id=?", (pid,))
    db.commit()
    db.close()
    flash('Property approved!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/reject/<int:pid>')
def reject_property(pid):
    if 'user_id' not in session or session['user_role'] != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    db.execute("UPDATE properties SET status='rejected' WHERE id=?", (pid,))
    db.commit()
    db.close()
    flash('Property rejected.', 'warning')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)