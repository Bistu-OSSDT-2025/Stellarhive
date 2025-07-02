from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, MultipleFileField
from wtforms.validators import DataRequired, Length

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