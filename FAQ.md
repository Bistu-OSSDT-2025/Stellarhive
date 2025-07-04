# Stellarhive 项目常见问题解答（FAQ）

**Q1: 启动项目时报 ModuleNotFoundError: No module named 'Stellarhive' 怎么办？**  
A1: 请在项目根目录下用 `python -m Stellarhive.app` 启动。

**Q2: 如何安装依赖？**  
A2: 在项目根目录下执行 `pip install -r Stellarhive/requirements.txt`。

**Q3: 如何初始化数据库？**  
A3: 执行 `flask db upgrade`。

**Q4: 访问网站时页面样式错乱？**  
A4: 请确保 static 目录下的资源文件齐全，且路径正确。

**Q5: 如何添加管理员？**  
A5: 请在数据库中手动设置用户的管理员标志，或联系开发者。

**Q6: 运行时 rewards.json 报错？**  
A6: 请确保 Stellarhive 目录下有 rewards.json 文件，或根据需求自行创建。 