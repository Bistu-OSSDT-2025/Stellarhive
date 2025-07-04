# Stellarhive 项目说明

Stellarhive 是一个集资源库、论坛、奖励中心、小游戏、用户系统于一体的综合性社区网站。用户可以上传下载资源、参与论坛讨论、每日签到获取积分、兑换虚拟商品、参与小游戏等。

## 主要功能
- **资源库**：文件上传、下载、分类、积分获取
- **论坛**：发帖、回帖、收藏、关注、编辑、删除
- **奖励中心**：每日签到、积分兑换、虚拟商品、装扮
- **游戏娱乐**：井字棋、连连看、五子棋
- **用户系统**：注册、登录、个人信息、头像自定义、积分展示
- **管理员功能**：成员管理、积分调整、内容审核

## 技术栈
- 后端：Python + Flask
- 前端：HTML5 + CSS3 + JavaScript + Jinja2
- 数据库：SQLite/MySQL

## 启动方式
在项目根目录下执行：
```bash
python -m Stellarhive.app
```

详细安装和使用说明请见 [INSTALL.md](INSTALL.md)。

## 功能特点

- 用户系统
  - 注册/登录
  - 个人资料管理
  - 积分系统
- 文件管理
  - 文件上传/下载
  - 文件分类标签
  - 个人文件管理
- 积分奖励系统
  - 每日签到
  - 上传奖励
  - 下载奖励
  - 学习奖励
- 游戏娱乐
  - 井字棋
  - 连连看
  - 五子棋
- 社区功能
  - 技术博客学习
  - 成员管理

## 技术栈

- 后端：Flask + SQLite
- 前端：HTML + CSS + JavaScript
- 依赖管理：pip

## 快速开始

1. 克隆项目
```bash
git clone https://github.com/Bistu-OSSDT-2025/Stellarhive.git
cd Stellarhive
```

2. 创建虚拟环境
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 运行项目
```bash
cd Stellarhive
python app.py
```

5. 访问网站
打开浏览器访问 http://localhost:5000

## 项目结构

```
Stellarhive/
├── app.py              # 主应用文件
├── models.py           # 数据模型
├── forms.py            # 表单类
├── requirements.txt    # 项目依赖
├── static/            # 静态文件
├── templates/         # HTML模板
├── uploads/          # 上传文件目录
└── instance/         # 实例配置
```

## 配置说明

- 数据库：SQLite
- 上传文件大小限制：5GB
- 默认管理员账号：
  - 用户名：Bruce
  - 密码：12345

## 贡献指南

1. Fork 本仓库
2. 创建新的分支 `git checkout -b feature/your-feature`
3. 提交更改 `git commit -am 'Add some feature'`
4. 推送到分支 `git push origin feature/your-feature`
5. 创建 Pull Request

## 开源协议

MIT License 