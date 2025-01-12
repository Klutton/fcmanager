from flask import Flask
from flask_jwt_extended import JWTManager
from user import user_bp  # 导入user蓝图
from fcapi import fc_bp  # 导入fc蓝图
from flask_cors import CORS
from datetime import timedelta


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "0ct4710-v-c06nt9npozval"  # 实际应用中应该使用环境变量
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=3)  # 设置token过期时间为3天
app.config["JWT_ERROR_MESSAGE_KEY"] = "message"  # 错误消息的key
jwt = JWTManager(app)
app.register_blueprint(user_bp)  # 注册user蓝图
app.register_blueprint(fc_bp)  # 注册fc蓝图
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

if __name__ == "__main__":
    app.run(debug=True)
