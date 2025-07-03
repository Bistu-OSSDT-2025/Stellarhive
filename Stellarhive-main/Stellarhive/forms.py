from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, MultipleFileField, FileField, TextAreaField, RadioField
from wtforms.validators import DataRequired, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 64)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')

class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 64)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('注册')

class UploadForm(FlaskForm):
    file = MultipleFileField('选择文件', validators=[DataRequired()])
    tags = StringField('标签（用逗号分隔）')
    submit = SubmitField('上传') 

class EditProfileForm(FlaskForm):
    nickname = StringField('昵称', validators=[Length(0, 64)])
    bio = StringField('个人简介', validators=[Length(0, 256)])
    submit = SubmitField('保存修改')

class AvatarUploadForm(FlaskForm):
    avatar = FileField('选择头像图片', validators=[DataRequired()])
    submit = SubmitField('上传头像')

class ForumPostForm(FlaskForm):
    title = StringField('标题', validators=[DataRequired(), Length(min=1, max=128)])
    content = TextAreaField('内容', validators=[DataRequired()])
    submit = SubmitField('发布')

class ForumCommentForm(FlaskForm):
    content = TextAreaField('评论', validators=[DataRequired()])
    submit = SubmitField('提交')

class CustomizeForm(FlaskForm):
    font = RadioField('昵称字体')
    color = RadioField('昵称颜色')
    frame = RadioField('头像框')
    submit = SubmitField('保存装扮')

class EmptyForm(FlaskForm):
    pass