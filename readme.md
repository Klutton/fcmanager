# FCManager

FCManager 是一个基于 Flask 的爬虫任务管理系统后端服务。

## 功能特性

- 用户管理
  - 用户注册/登录
  - JWT 认证
  - 用户信息管理
- 任务管理
  - 创建爬虫任务
  - 任务审核流程
  - 任务状态查询
  - 任务修改
- 数据库支持
  - PostgreSQL 数据库
  - 自动初始化数据表

## 技术栈

- Python 3.10
- Flask
- Flask-JWT-Extended
- Flask-CORS
- PostgreSQL
- bcrypt

## 安装

1. 克隆仓库

```bash
git clone https://github.com/你的用户名/fcmanager.git
cd fcmanager
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置数据库
- 确保已安装PostgreSQL
- 创建数据库fcmanager
- 修改database.py中的数据库连接参数

4. 运行服务

```bash
python main.py
```

## API 接口

[https://apifox.com/apidoc/shared-886b9da0-d0c7-4ec4-b12b-532182f07ff7](https://apifox.com/apidoc/shared-886b9da0-d0c7-4ec4-b12b-532182f07ff7)

### 用户相关

- POST `/user/register` - 用户注册
- POST `/user/login` - 用户登录
- GET `/user/profile/get` - 获取用户信息
- POST `/user/profile/update` - 更新用户信息

### 任务相关

- POST `/fctask/create` - 创建任务
- POST `/fctask/audit` - 审核任务
- GET `/fctask/get` - 获取任务列表
- POST `/fctask/modify` - 修改任务
- GET `/fctask/info` - 获取任务状态

## 配置说明

主要配置项在 server.py 中:

- JWT_SECRET_KEY: JWT密钥
- JWT_ACCESS_TOKEN_EXPIRES: Token过期时间
- CORS配置: 允许的源和方法

## 开发说明

- 使用Blueprint模式组织路由
- 统一的错误处理和响应格式
- 参数化SQL查询防注入
- 密码加密存储

## 许可证

MIT License