from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, Response, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, File, Reward, TaskLog
from forms import LoginForm, RegisterForm, UploadForm
from flask_wtf.csrf import CSRFProtect
import os, json, datetime, random
from io import BytesIO
from werkzeug.exceptions import RequestEntityTooLarge
from forms import EditProfileForm
from functools import wraps


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stellarhive-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'stellarhive.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB
app.config['WTF_CSRF_SECRET_KEY'] = 'stellarhive-csrf-secret-key'
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect()
csrf.init_app(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # type: ignore

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'ok': False, 'msg': '未登录或登录已过期，请重新登录'}), 401

@app.before_request
def create_tables():
    if not getattr(app, '_tables_created', False):
        db.create_all()
        # 导入奖励内容
        if Reward.query.count() == 0:
            try:
                with open('rewards.json', encoding='utf-8') as f:
                    rewards = json.load(f)
                    for r in rewards:
                        db.session.add(Reward(**r))
                    db.session.commit()
            except Exception as e:
                print('奖励导入失败:', e)
        # 自动创建管理员账号
        if not User.query.filter_by(username='Bruce').first():
            admin = User()
            admin.username = 'Bruce'
            admin.role = 'admin'
            admin.set_password('12345')
            db.session.add(admin)
            db.session.commit()
        setattr(app, '_tables_created', True)

@app.route('/')
def index():
    files = File.query.all()
    return render_template('index.html', files=files)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('用户名或密码错误')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在')
        else:
            user = User()
            user.username = form.username.data
            user.role = 'user'
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请登录')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        uploader_id = current_user.id
        tag_map = {
            'pdf': '文档', 'doc': '文档', 'docx': '文档', 'txt': '文档', 'md': '文档',
            'jpg': '图片', 'jpeg': '图片', 'png': '图片', 'gif': '图片', 'bmp': '图片',
            'zip': '压缩包', 'rar': '压缩包', '7z': '压缩包',
            'py': '代码', 'js': '代码', 'java': '代码', 'cpp': '代码', 'c': '代码', 'ts': '代码',
            'xls': '表格', 'xlsx': '表格', 'csv': '表格',
            'ppt': '演示', 'pptx': '演示',
        }
        total_size = 0
        for f in form.file.data:
            filename = f.filename
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(save_path)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            tags = tag_map.get(ext, ext if ext else '其他')
            file_record = File()
            file_record.filename = filename
            file_record.uploader_id = uploader_id
            file_record.size = os.path.getsize(save_path)
            file_record.tags = tags
            db.session.add(file_record)
            total_size += file_record.size
        db.session.commit()
        # 上传奖励：每100kb加1分，四舍五入
        upload_score = round(total_size / 102400)
        if upload_score > 0:
            current_user.score += upload_score
            db.session.commit()
            flash(f'上传成功，奖励{upload_score}积分！')
        else:
            flash('上传成功')
        # 激励系统：上传奖励日志
        TaskLog.log_task(current_user.id, 'upload', upload_score)
        return redirect(url_for('index'))
    return render_template('upload.html', form=form)

@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    if current_user.role != 'admin':
        flash('只有管理员可以删除文件')
        return redirect(url_for('index'))
    file = File.query.get_or_404(file_id)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(file)
        db.session.commit()
        flash('文件已删除')
    except Exception as e:
        flash('删除失败: {}'.format(e))
    return redirect(url_for('index'))

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    file = File.query.get_or_404(file_id)
    # 下载奖励：每10mb加1分，四舍五入
    download_score = round(file.size / (10 * 1024 * 1024))
    if download_score > 0:
        current_user.score += download_score
        db.session.commit()
        flash(f'下载成功，奖励{download_score}积分！')
    TaskLog.log_task(current_user.id, 'download', download_score)
    return send_from_directory(app.config['UPLOAD_FOLDER'], file.filename, as_attachment=True)

@app.route('/rewards')
@login_required
def rewards():
    rewards = Reward.query.all()
    logs = TaskLog.query.filter_by(user_id=current_user.id).all()
    # 检查今日是否已签到
    today = datetime.date.today()
    is_signed = TaskLog.query.filter_by(
        user_id=current_user.id,
        task='sign_in',
        date=today
    ).first() is not None
    return render_template('rewards.html', rewards=rewards, logs=logs, is_signed=is_signed)

@app.route('/sign_in')
@login_required
def sign_in():
    today = datetime.date.today()
    log = TaskLog.query.filter_by(user_id=current_user.id, task='sign_in', date=today).first()
    if log:
        flash('今日已签到')
    else:
        TaskLog.log_task(current_user.id, 'sign_in', 5)
        current_user.score += 5  # 每日签到加5分
        db.session.commit()
        flash('签到成功，奖励已发放！（+5积分）')
    return redirect(url_for('rewards'))

@app.route('/learn_blog_page', methods=['GET', 'POST'])
@login_required
def learn_blog_page():
    if request.method == 'POST':
        # 领取奖励
        current_user.score += 10
        db.session.commit()
        TaskLog.log_task(current_user.id, 'learn_blog', 10)
        flash('学习技术博客成功，奖励10分！')
        return redirect(url_for('rewards'))
    # 随机选一篇博客
    with open(os.path.join(basedir, 'blog_links.json'), encoding='utf-8') as f:
        blogs = json.load(f)
        blog = random.choice(blogs)
    return render_template('learn_blog.html', blog=blog)

@app.route('/library')
def library():
    files = File.query.all()
    with open(os.path.join(basedir, 'blog_links.json'), encoding='utf-8') as f:
        blogs = json.load(f)
    return render_template('library.html', files=files, blogs=blogs)

@app.route('/myfiles')
@login_required
def myfiles():
    files = File.query.filter_by(uploader_id=current_user.id).all()
    return render_template('myfiles.html', files=files)

def csrf_exempt(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)
    return csrf.exempt(wrapped)

@app.route('/myfile_delete/<int:file_id>', methods=['POST'])
@login_required
@csrf_exempt
def myfile_delete(file_id):
    file = File.query.get_or_404(file_id)
    if file.uploader_id != current_user.id:
        flash('只能删除自己上传的文件')
        return redirect(url_for('myfiles'))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(file)
        db.session.commit()
        flash('文件已删除')
    except Exception as e:
        flash('删除失败: {}'.format(e))
    return redirect(url_for('myfiles'))

@app.route('/myfiles_batch_delete', methods=['POST'])
@login_required
@csrf_exempt
def myfiles_batch_delete():
    file_ids = request.form.getlist('file_ids')
    if not file_ids:
        flash('请选择要删除的文件')
        return redirect(url_for('myfiles'))
    files = File.query.filter(File.id.in_(file_ids), File.uploader_id==current_user.id).all()
    for file in files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(file)
    db.session.commit()
    flash('批量删除成功')
    return redirect(url_for('myfiles'))

@app.route('/myfiles_batch_download', methods=['POST'])
@login_required
@csrf_exempt
def myfiles_batch_download():
    file_ids = request.form.getlist('file_ids')
    if not file_ids:
        flash('请选择要下载的文件')
        return redirect(url_for('myfiles'))
    files = File.query.filter(File.id.in_(file_ids), File.uploader_id==current_user.id).all()
    if len(files) == 1:
        file = files[0]
        return send_from_directory(app.config['UPLOAD_FOLDER'], file.filename, as_attachment=True)
    # 多文件，返回多个响应流
    def generate():
        for file in files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file_stream:
                    yield f'\n----- {file.filename} -----\n'.encode('utf-8')
                    yield file_stream.read()
    return Response(generate(), mimetype='application/octet-stream', headers={
        'Content-Disposition': 'attachment; filename="multi_files.txt"'
    })

@app.route('/library_batch_download', methods=['POST'])
def library_batch_download():
    file_ids = request.form.getlist('file_ids')
    if not file_ids:
        flash('请选择要下载的文件')
        return redirect(url_for('library'))
    files = File.query.filter(File.id.in_(file_ids)).all()
    if len(files) == 1:
        file = files[0]
        return send_from_directory(app.config['UPLOAD_FOLDER'], file.filename, as_attachment=True)
    def generate():
        for file in files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file_stream:
                    yield f'\n----- {file.filename} -----\n'.encode('utf-8')
                    yield file_stream.read()
    return Response(generate(), mimetype='application/octet-stream', headers={
        'Content-Disposition': 'attachment; filename="multi_files.txt"'
    })


@app.route('/members', methods=['GET', 'POST'])
@login_required
def members():
    if request.method == 'POST' and current_user.role == 'admin':
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        user = User.query.get(user_id)
        if user:
            if action == 'add':
                user.score += 10
            elif action == 'sub':
                user.score = max(0, user.score - 10)
            db.session.commit()
            flash(f'已为 {user.username} {"加" if action=="add" else "减"}10分')
        return redirect(url_for('members'))
    users = User.query.all()
    return render_template('members.html', users=users)

@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash('个人信息已更新')
        return redirect(url_for('profile', user_id=current_user.id))
    form.nickname.data = current_user.nickname
    form.bio.data = current_user.bio
    return render_template('edit_profile.html', form=form)

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return '''<script>alert("文件过大，上传失败（单次最大5GB）");window.history.back();</script>''', 413

@app.route('/tic_tac_toe')
def tic_tac_toe():
    return render_template('tic_tac_toe.html')

@app.route('/link_game')
def link_game():
    return render_template('link_game.html')

@app.route('/game_reward')
@login_required
def game_reward():
    game_type = request.args.get('type')
    if game_type == 'link_game':
        current_user.score += 60
        db.session.commit()
        TaskLog.log_task(current_user.id, 'link_game', 60)
        return jsonify({'ok': True, 'msg': '连连看胜利，奖励60分！'})
    elif game_type == 'tic_tac_toe':
        current_user.score += 20
        db.session.commit()
        TaskLog.log_task(current_user.id, 'tic_tac_toe', 20)
        return jsonify({'ok': True, 'msg': '井字棋胜利，奖励20分！'})
    elif game_type == 'gomoku':
        current_user.score += 80
        db.session.commit()
        TaskLog.log_task(current_user.id, 'gomoku', 80)
        return jsonify({'ok': True, 'msg': '五子棋胜利，奖励80分！'})
    else:
        return jsonify({'ok': False, 'msg': '未知游戏类型'}), 400

@app.route('/get_score')
@login_required
def get_score():
    return jsonify({'score': current_user.score})

@app.route('/gomoku')
def gomoku():
    return render_template('gomoku.html')

@app.route('/consume_score', methods=['POST'])
@login_required
@csrf_exempt
def consume_score():
    data = request.get_json()
    amount = int(data.get('amount', 0))
    if current_user.score < amount:
        return jsonify({'ok': False, 'msg': '积分不足！', 'score': current_user.score})
    current_user.score -= amount
    db.session.commit()
    return jsonify({'ok': True, 'score': current_user.score})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True) 