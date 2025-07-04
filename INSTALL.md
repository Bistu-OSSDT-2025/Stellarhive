# Stellarhive 安装说明

## 1. 环境要求
- Python 3.8 及以上
- pip 包管理器

## 2. 安装依赖
在项目根目录下执行：
```bash
pip install -r Stellarhive/requirements.txt
```

## 3. 数据库初始化
如需使用数据库迁移功能，请先初始化数据库：
```bash
flask db upgrade
```

## 4. 启动项目
在项目根目录下执行：
```bash
python -m Stellarhive.app
```

## 5. 访问网站
在浏览器中访问：
- http://localhost:5000
- 或 http://你的服务器IP:5000

如遇依赖缺失，请根据报错信息使用 pip 安装相应库。 