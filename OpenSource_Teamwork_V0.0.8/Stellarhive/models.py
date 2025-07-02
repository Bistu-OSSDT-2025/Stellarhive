from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), default='user')  # 'admin' or 'user'
    score = db.Column(db.Integer, default=0)  # 积分，默认为0
    nickname = db.Column(db.String(64), default='')  # 昵称
    bio = db.Column(db.String(256), default='')      # 个人简介

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(128), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    size = db.Column(db.Integer)
    upload_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    tags = db.Column(db.String(128), default='')  # 逗号分隔标签

class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    link = db.Column(db.String(256))
    description = db.Column(db.String(256))

class TaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    task = db.Column(db.String(32))  # 'upload', 'download', 'sign_in', 'game'
    amount = db.Column(db.Integer, default=0)  # 上传/下载的字节数
    date = db.Column(db.Date, default=datetime.date.today)

    @staticmethod
    def log_task(user_id, task, amount=0):
        log = TaskLog(user_id=user_id, task=task, amount=amount, date=datetime.date.today())
        db.session.add(log)
        db.session.commit() 