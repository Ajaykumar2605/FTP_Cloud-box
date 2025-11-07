#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, abort, jsonify
import os, stat, shutil, zipfile, datetime, subprocess
from werkzeug.utils import secure_filename, safe_join

STORAGE_ROOT = "/mnt/shared/ftpshare"
USERS = {
    "admin": {"password": "admin", "is_admin": True},
    "ftpguest": {"password": "ftpguest", "is_admin": False},
    "ftpuser": {"password": "ftpuser", "is_admin": False},
}

app = Flask(__name__)
app.secret_key = "supersecretkey"

@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.datetime.fromtimestamp(float(value)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return value

# === Utility functions ===
def user_root():
    username = session.get("username")
    if not username:
        abort(403)
    path = STORAGE_ROOT if username == "admin" else os.path.join(STORAGE_ROOT, username)
    os.makedirs(path, exist_ok=True)
    return path

def secure_path(path):
    abs_path = safe_join(user_root(), path)
    if not abs_path:
        abort(403)
    return abs_path

def get_permissions(path):
    mode = os.stat(path).st_mode
    return stat.filemode(mode)

# Faster & accurate folder size using 'du -sb'
def get_dir_size(path):
    try:
        result = subprocess.run(["du", "-sb", path], capture_output=True, text=True)
        size = int(result.stdout.split()[0])
    except Exception:
        size = 0
    return size

# === Authentication ===
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            os.makedirs(user_root(), exist_ok=True)
            return redirect(url_for("browse"))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.before_request
def require_login():
    if request.endpoint not in ("login", "static") and "username" not in session:
        return redirect(url_for("login"))

# === Browse Route ===
@app.route("/browse/", defaults={"path": ""})
@app.route("/browse/<path:path>")
def browse(path):
    abs_path = secure_path(path)
    if not os.path.exists(abs_path):
        abort(404)

    items = []
    if path:
        items.append(("..", "dir", "-", "-", "-"))

    for name in sorted(os.listdir(abs_path)):
        full_path = os.path.join(abs_path, name)
        type_ = "dir" if os.path.isdir(full_path) else "file"
        size = os.path.getsize(full_path) if os.path.isfile(full_path) else "-"
        modified = os.path.getmtime(full_path)
        perms = get_permissions(full_path)
        items.append((name, type_, size, modified, perms))

    # === Disk usage info ===
    total, used, free = shutil.disk_usage("/mnt/shared")
    total_gb = total / (1024**3)
    used_gb = used / (1024**3)
    used_percent = round((used / total) * 100, 1)

    # === Dynamic user usage ===
    admin_space = get_dir_size(os.path.join(STORAGE_ROOT, "admin"))
    ftpguest_space = get_dir_size(os.path.join(STORAGE_ROOT, "ftpguest"))
    ftpuser_space = get_dir_size(os.path.join(STORAGE_ROOT, "ftpuser"))

    assigned_space = admin_space + ftpguest_space + ftpuser_space
    free_segment = max(total - assigned_space, 0)

    # === Convert to percentages ===
    admin_pct = (admin_space / total) * 100 if total > 0 else 0
    ftpguest_pct = (ftpguest_space / total) * 100 if total > 0 else 0
    ftpuser_pct = (ftpuser_space / total) * 100 if total > 0 else 0
    free_pct = (free_segment / total) * 100 if total > 0 else 0

    # === Bar color logic ===
    if used_percent < 70:
        bar_color = "#22c55e"
    elif used_percent < 90:
        bar_color = "#facc15"
    else:
        bar_color = "#ef4444"

    return render_template(
        "browser.html",
        files=items,
        current_path=path,
        username=session.get("username", "guest"),
        os=os,
        used_gb=round(used_gb, 1),
        total_gb=round(total_gb, 1),
        used_percent=used_percent,
        admin_pct=admin_pct,
        ftpguest_pct=ftpguest_pct,
        ftpuser_pct=ftpuser_pct,
        free_pct=free_pct,
        bar_color=bar_color
    )

# === Live AJAX endpoint ===
@app.route("/api/storage")
def api_storage():
    total, used, free = shutil.disk_usage("/mnt/shared")

    admin_space = get_dir_size(os.path.join(STORAGE_ROOT, "admin"))
    ftpguest_space = get_dir_size(os.path.join(STORAGE_ROOT, "ftpguest"))
    ftpuser_space = get_dir_size(os.path.join(STORAGE_ROOT, "ftpuser"))

    assigned_space = admin_space + ftpguest_space + ftpuser_space
    free_segment = max(total - assigned_space, 0)

    total_gb = total / (1024**3)
    used_gb = used / (1024**3)
    used_percent = round((used / total) * 100, 1)

    if used_percent < 70:
        bar_color = "#22c55e"
    elif used_percent < 90:
        bar_color = "#facc15"
    else:
        bar_color = "#ef4444"

    return jsonify({
        "used_gb": round(used_gb, 1),
        "total_gb": round(total_gb, 1),
        "used_percent": used_percent,
        "bar_color": bar_color,
        "segments": {
            "admin": round((admin_space / total) * 100, 2),
            "ftpguest": round((ftpguest_space / total) * 100, 2),
            "ftpuser": round((ftpuser_space / total) * 100, 2),
            "free": round((free_segment / total) * 100, 2)
        }
    })

# === File operations (same as before) ===
# @app.route("/upload/", methods=["POST"])
# @app.route("/upload/<path:path>", methods=["POST"])
# def upload(path=""):
#     abs_path = secure_path(path)
#     os.makedirs(abs_path, exist_ok=True)
#     files = request.files.getlist("file")
#     for file in files:
#         if file and file.filename:
#             filename = secure_filename(file.filename)
#             file.save(os.path.join(abs_path, filename))
#     return redirect(url_for("browse", path=path))
@app.route("/upload/", methods=["POST"])
@app.route("/upload/<path:path>", methods=["POST"])
def upload(path=""):
    abs_path = secure_path(path)
    os.makedirs(abs_path, exist_ok=True)
    files = request.files.getlist("file")
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(abs_path, filename))
    return '', 200  # no redirect, handled by JS


@app.route("/delete/<path:path>")
def delete_file(path):
    abs_path = secure_path(path)
    if os.path.exists(abs_path):
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
    return redirect(url_for("browse", path=os.path.dirname(path)))

@app.route("/create_folder")
def create_folder():
    path = request.args.get("path", "")
    name = request.args.get("name")
    if not name: return redirect(url_for("browse", path=path))
    abs_path = secure_path(os.path.join(path, name))
    os.makedirs(abs_path, exist_ok=True)
    return redirect(url_for("browse", path=path))

@app.route("/create_file")
def create_file():
    path = request.args.get("path", "")
    name = request.args.get("name")
    if not name: return redirect(url_for("browse", path=path))
    abs_path = secure_path(os.path.join(path, name))
    open(abs_path, "w").close()
    return redirect(url_for("browse", path=path))

@app.route("/rename_item")
def rename_item():
    path = request.args.get("path", "")
    old_name = request.args.get("old_name")
    new_name = request.args.get("new_name")
    if not old_name or not new_name: return redirect(url_for("browse", path=path))
    old_path = secure_path(os.path.join(path, old_name))
    new_path = secure_path(os.path.join(path, new_name))
    os.rename(old_path, new_path)
    return redirect(url_for("browse", path=path))

@app.route("/compress_folder")
def compress_folder():
    path = request.args.get("path", "")
    name = request.args.get("name")
    folder_path = secure_path(os.path.join(path, name))
    zip_path = folder_path + ".zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
    shutil.make_archive(folder_path, 'zip', folder_path)
    return redirect(url_for("browse", path=path))

@app.route("/download/<path:path>")
def download(path):
    abs_path = secure_path(path)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_from_directory(os.path.dirname(abs_path), os.path.basename(abs_path), as_attachment=True)

@app.route("/download_folder/<path:path>")
def download_folder(path):
    abs_path = secure_path(path)
    if not os.path.isdir(abs_path):
        abort(404)
    zip_path = abs_path + ".zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
    shutil.make_archive(abs_path, 'zip', abs_path)
    return send_from_directory(os.path.dirname(abs_path), os.path.basename(zip_path), as_attachment=True)

# === Main Entry ===
if __name__ == "__main__":
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    for user in USERS:
        os.makedirs(os.path.join(STORAGE_ROOT, user), exist_ok=True)
    print("?? FTP-Box running on http://0.0.0.0:8008")
    app.run(host="0.0.0.0", port=8008)
