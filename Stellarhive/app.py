from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, Response, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, File, Reward, TaskLog, ForumCategory, ForumPost, ForumComment, ForumLike
from forms import LoginForm, RegisterForm, UploadForm, AvatarUploadForm, ForumPostForm, ForumCommentForm
from flask_wtf.csrf import CSRFProtect
import os, json, datetime, random
from io import BytesIO
from werkzeug.exceptions import RequestEntityTooLarge
from forms import EditProfileForm
from functools import wraps
from PIL import Image
import uuid


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stellarhive-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'stellarhive.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
app.config['AVATAR_FOLDER'] = os.path.join(basedir, 'avatars')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB
app.config['WTF_CSRF_SECRET_KEY'] = 'stellarhive-csrf-secret-key'
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect()
csrf.init_app(app)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

if not os.path.exists(app.config['AVATAR_FOLDER']):
    os.makedirs(app.config['AVATAR_FOLDER'])

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
        # 创建默认论坛分类
        if ForumCategory.query.count() == 0:
            categories = [
                {'name': '公告通知', 'description': '重要公告和通知'},
                {'name': '技术讨论', 'description': '分享和讨论技术问题'},
                {'name': '资源分享', 'description': '分享有价值的学习资源'},
                {'name': '问题求助', 'description': '寻求帮助和解答'},
                {'name': '闲聊灌水', 'description': '轻松话题讨论区'}
            ]
            for category in categories:
                db.session.add(ForumCategory(**category))
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

@app.route('/unlock_avatar', methods=['POST'])
@login_required
@csrf_exempt
def unlock_avatar():
    """解锁自定义头像权限"""
    if current_user.score < 100:
        return jsonify({'ok': False, 'msg': '积分不足！需要100积分解锁自定义头像功能', 'score': current_user.score})
    
    current_user.score -= 100
    current_user.avatar_enabled = True
    db.session.commit()
    TaskLog.log_task(current_user.id, 'unlock_avatar', 100)
    return jsonify({'ok': True, 'msg': '成功解锁自定义头像功能！', 'score': current_user.score})

@app.route('/upload_avatar', methods=['GET', 'POST'])
@login_required
def upload_avatar():
    """上传头像"""
    if not current_user.avatar_enabled:
        flash('您还没有解锁自定义头像功能，需要100积分解锁')
        return redirect(url_for('rewards'))
    
    form = AvatarUploadForm()
    if form.validate_on_submit():
        file = form.avatar.data
        if file:
            # 生成唯一文件名
            filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
            
            try:
                # 打开图片
                img = Image.open(file.stream)
                
                # 转换为RGB模式
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 调整尺寸为正方形
                size = (200, 200)
                # 计算裁剪区域，保持比例
                width, height = img.size
                if width > height:
                    left = (width - height) // 2
                    img = img.crop((left, 0, left + height, height))
                elif height > width:
                    top = (height - width) // 2
                    img = img.crop((0, top, width, top + width))
                
                # 调整到目标尺寸
                img = img.resize(size, Image.Resampling.LANCZOS)
                
                # 保存为PNG格式
                img.save(filepath, 'PNG')
                
                # 更新用户头像信息
                current_user.avatar_filename = filename
                db.session.commit()
                
                flash('头像上传成功！')
                return redirect(url_for('profile', user_id=current_user.id))
                
            except Exception as e:
                flash(f'头像上传失败：{str(e)}')
                return redirect(url_for('upload_avatar'))
    
    return render_template('upload_avatar.html', form=form)

@app.route('/avatar/<filename>')
def avatar(filename):
    """提供头像文件访问"""
    return send_from_directory(app.config['AVATAR_FOLDER'], filename)

@app.route('/remove_avatar', methods=['POST'])
@login_required
@csrf_exempt
def remove_avatar():
    """删除头像"""
    if current_user.avatar_filename:
        # 删除文件
        filepath = os.path.join(app.config['AVATAR_FOLDER'], current_user.avatar_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # 清除数据库记录
        current_user.avatar_filename = ''
        db.session.commit()
        flash('头像已删除')
    
    return redirect(url_for('profile', user_id=current_user.id))

@app.route('/shop')
@login_required
def shop():
    return render_template('shop.html')

@app.route('/exchange', methods=['POST'])
@login_required
@csrf_exempt
def exchange():
    data = request.get_json()
    type_ = data.get('type')
    value = data.get('value')
    cost = int(data.get('cost', 0))
    if current_user.score < cost:
        return jsonify({'ok': False, 'msg': '积分不足！'})
    # 头像框
    if type_ == 'avatar_frame':
        current_user.score -= cost
        current_user.avatar_frame = value  # 你需要在User模型加avatar_frame字段
    # 昵称颜色
    elif type_ == 'nickname_color':
        current_user.score -= cost
        current_user.nickname_color = value  # 你需要在User模型加nickname_color字段
    # 昵称字体
    elif type_ == 'nickname_font':
        current_user.score -= cost
        current_user.nickname_font = value  # 你需要在User模型加nickname_font字段
    else:
        return jsonify({'ok': False, 'msg': '类型错误'})
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/forum')
@login_required
def forum():
    categories = ForumCategory.query.all()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 获取筛选参数
    category_id = request.args.get('category_id', type=int)
    sort_by = request.args.get('sort', 'newest')  # newest, popular, no_reply
    
    # 构建查询
    query = ForumPost.query
    
    # 如果指定了分类，则筛选
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # 排序
    if sort_by == 'popular':
        query = query.order_by(ForumPost.views.desc())
    elif sort_by == 'no_reply':
        query = query.outerjoin(ForumComment).group_by(ForumPost.id).having(db.func.count(ForumComment.id) == 0)
    else:  # newest
        query = query.order_by(ForumPost.created_time.desc())
    
    # 分页
    posts = query.paginate(page=page, per_page=per_page)
    
    return render_template('forum.html', 
                         categories=categories, 
                         posts=posts,
                         current_category_id=category_id,
                         sort_by=sort_by)

@app.route('/forum/category/<int:category_id>')
@login_required
def forum_category(category_id):
    category = ForumCategory.query.get_or_404(category_id)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    posts = ForumPost.query.filter_by(category_id=category_id).order_by(ForumPost.created_time.desc()).paginate(page=page, per_page=per_page)
    return render_template('forum_category.html', category=category, posts=posts, ForumPost=ForumPost)

@app.route('/forum/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def forum_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    form = ForumCommentForm()
    
    # 增加浏览量
    post.views += 1
    db.session.commit()
    
    if form.validate_on_submit() and current_user.is_authenticated:
        comment = ForumComment()
        comment.content = form.content.data
        comment.author_id = current_user.id
        comment.post_id = post.id
        db.session.add(comment)
        db.session.commit()
        flash('评论发布成功！')
        return redirect(url_for('forum_post', post_id=post_id))
        
    comments = post.comments.order_by(ForumComment.created_time.desc()).all()
    return render_template('forum_post.html', post=post, form=form, comments=comments)

@app.route('/forum/new_post/<int:category_id>', methods=['POST'])
@login_required
def forum_new_post(category_id):
    if not current_user.is_authenticated:
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': '请先登录后再发帖'}), 401
        flash('请先登录后再发帖', 'warning')
        return redirect(url_for('login'))
    
    # 检查Content-Type
    if request.headers.get('Content-Type') == 'application/json':
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
    else:
        title = request.form.get('title')
        content = request.form.get('content')
    
    if not title or not content:
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': '标题和内容不能为空'}), 400
        flash('标题和内容不能为空', 'warning')
        return redirect(url_for('forum'))
    
    try:
        category = ForumCategory.query.get_or_404(category_id)
        
        # 创建新帖子
        post = ForumPost()
        post.title = title
        post.content = content
        post.author_id = current_user.id
        post.category_id = category.id
        
        db.session.add(post)
        db.session.commit()
        
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'redirect': url_for('forum_post', post_id=post.id),
                'message': '发帖成功！'
            })
            
        flash('发帖成功！', 'success')
        return redirect(url_for('forum_post', post_id=post.id))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'error': str(e) or '发帖失败，请重试'}), 500
        flash('发帖失败，请重试', 'error')
        return redirect(url_for('forum'))

@app.route('/forum/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != 'admin':
        flash('你没有权限编辑这个帖子', 'error')
        return redirect(url_for('forum_post', post_id=post_id))
    
    form = ForumPostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('帖子已更新', 'success')
        return redirect(url_for('forum_post', post_id=post_id))
    
    return render_template('forum_edit_post.html', form=form, post=post)

@app.route('/forum/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role != 'admin':
        flash('你没有权限删除这个帖子', 'error')
        return redirect(url_for('forum_post', post_id=post_id))
    
    category_id = post.category_id
    db.session.delete(post)
    db.session.commit()
    flash('帖子已删除', 'success')
    return redirect(url_for('forum_category', category_id=category_id))

@app.route('/forum/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = ForumComment.query.get_or_404(comment_id)
    if comment.author_id != current_user.id and current_user.role != 'admin':
        flash('你没有权限删除这个评论', 'error')
        return redirect(url_for('forum_post', post_id=comment.post_id))
    
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    flash('评论已删除', 'success')
    return redirect(url_for('forum_post', post_id=post_id))

@app.route('/forum/like/<int:post_id>', methods=['POST'])
@login_required
@csrf_exempt
def toggle_like(post_id):
    if not current_user.is_authenticated:
        return jsonify({'error': '请先登录'}), 401
        
    post = ForumPost.query.get_or_404(post_id)
    like = ForumLike.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        like = ForumLike(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        action = 'liked'
    
    db.session.commit()
    return jsonify({
        'ok': True,
        'action': action,
        'likes': post.likes.count()
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True) 