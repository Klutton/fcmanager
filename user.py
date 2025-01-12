from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from database import (
    login as db_login,
    create_user,
    get_profile,
    update_or_create_profile,
    get_username,
)

# 创建蓝图实例
user_bp = Blueprint("user", __name__, url_prefix="/user")


# 定义路由
@user_bp.route("/profile/get", methods=["GET"])
@jwt_required()
def profile():
    try:
        # user_id = request.args.get("user_id", type=int)
        # if user_id and isadmin
        # if not user_id:
        user_id = int(get_jwt_identity())
            
        try:
            profile_data = get_profile(user_id)
        except ValueError:  # 捕获用户档案不存在的错误
            username = get_username(user_id)  # 使用新函数获取用户名
            # 使用已有的update_or_create_profile函数创建默认档案
            update_or_create_profile(user_id, username, "", "")
            profile_data = get_profile(user_id)
            
        return jsonify({
            "success": True,
            "data": profile_data
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@user_bp.route("/profile/update", methods=["POST"])
@jwt_required()
def update_profile():
    try:
        # 将字符串类型的user_id转换为整数
        current_user_id = int(get_jwt_identity())
        form = request.form
        nickname = form.get("nickname")
        name = form.get("name")
        department = form.get("department")

        if not all([nickname, name, department]):
            return jsonify({"success": False, "message": "缺少必要参数"}), 400

        message = update_or_create_profile(current_user_id, nickname, name, department)
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@user_bp.route("/register", methods=["POST"])
def register():
    try:
        form = request.form
        username = form.get("username")
        password = form.get("password")

        if not all([username, password]):
            return jsonify({"success": False, "message": "缺少必要参数"}), 400

        message = create_user(username, password)
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@user_bp.route("/login", methods=["POST"])
def login():
    try:
        form = request.form
        username = form.get("username")
        password = form.get("password")

        if not all([username, password]):
            return jsonify({"success": False, "message": "缺少用户名或密码"}), 400

        user_id, message = db_login(username, password)

        # 将user_id转换为字符串
        access_token = create_access_token(identity=str(user_id))

        return jsonify(
            {"success": True, "message": message, "access_token": access_token}
        ), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
