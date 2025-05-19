# 书店销售管理系统

## 概要

使用Django开发的B/S数据库管理系统，学习[MDN的教程](https://github.com/mdn/django-locallibrary-tutorial)做的

模型如下
![ER diagram](BookstoreSalesManagementSystem/data/ER_diagram.png)


## 开始

```bash
# 安装依赖
pip3 install -r requirement.txt
# 添加数据
python3 manage.py makemigrations
python3 manage.py import_books data/data.json
python3 manage.py migrate
# 创建用户
python3 manage.py createsuperuser
# 运行服务器
python3 manage.py runserver
```

- 在网页`127.0.0.1`可以看到主界面

- 在网页`127.0.0.1:8000/admin`进入管理员界面
