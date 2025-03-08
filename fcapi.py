from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import (
    create_task,
    get_tasks,
    approve_task,
    modify_task,
    DatabaseError,
    get_user_role,
)
from fcmanager import create_crawl_task, get_crawl_status, cancel_crawl_task

# 创建蓝图实例
fc_bp = Blueprint("fctask", __name__, url_prefix="/fctask")

# 为整个蓝图添加JWT认证
@fc_bp.before_request
@jwt_required()
def before_request():
    pass

@fc_bp.route("/create", methods=["POST"])
def create_fctask():
    try:
        # 获取当前用户ID
        current_user_id = get_jwt_identity()

        # 获取请求参数
        form = request.form
        name = form.get("name")
        description = form.get("description")
        category = form.get("category")
        site_url = form.get("site_url")
        schedule = form.get("schedule")

        # 验证必要参数
        if not all([name, category, site_url]):
            return jsonify({"success": False, "message": "缺少必要参数"}), 400

        # 获取用户角色
        user_role = get_user_role(current_user_id)

        # 根据用户角色设置任务状态和其他参数
        is_admin = user_role == "admin"
        task_status = "approved" if is_admin else "pending"
        reviewer_id = current_user_id if is_admin else None
        fc_task_id = None

        # 如果是管理员，创建爬虫任务
        if is_admin:
            fc_response = create_crawl_task(
                url=site_url, name=name, description=description, schedule=schedule
            )
            fc_task_id = fc_response.get("id")

        # 创建数据库任务记录
        message = create_task(
            applicant_id=current_user_id,
            name=name,
            description=description,
            category=category,
            site_url=site_url,
            status=task_status,
            reviewer_id=reviewer_id,
            schedule=schedule,
            fc_task_id=fc_task_id,
        )

        return jsonify(
            {
                "success": True,
                "message": message,
                "data": {"fc_task_id": fc_task_id} if fc_task_id else None,
            }
        ), 200

    except DatabaseError as e:
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        return jsonify({"success": False, "message": f"创建任务失败: {str(e)}"}), 500


@fc_bp.route("/audit", methods=["POST"])
def audit_fctask():
    try:
        # 获取当前用户ID和角色
        admin_id = int(get_jwt_identity())
        user_role = get_user_role(admin_id)
        
        # 检查是否为管理员
        if user_role != "admin":
            return jsonify({"success": False, "message": ""}), 403

        # 获取请求参数
        form = request.form
        task_id = form.get("task_id")
        is_approved = form.get("is_approved")

        if not task_id or is_approved is None:
            return jsonify(
                {"success": False, "message": "缺少必要参数task_id或is_approved"}
            ), 400

        # 调用database审核任务
        response = approve_task(
            task_id=task_id, admin_id=admin_id, is_approved=is_approved
        )

        return jsonify(
            {"success": True, "data": response, "message": "任务审核成功"}
        ), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"任务审核失败: {str(e)}"}), 500


@fc_bp.route("/get", methods=["GET"])
def get_fctask():
    try:
        # 获取查询参数
        user_id = int(get_jwt_identity())
        status = request.args.get("status")
        category = request.args.get("category")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)

        # 调用database获取任务列表
        response = get_tasks(
            user_id=user_id,
            status=status,
            category=category,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )

        return jsonify(
            {"success": True, "data": response, "message": "获取任务列表成功"}
        ), 200

    except Exception as e:
        return jsonify(
            {"success": False, "message": f"获取任务列表失败: {str(e)}"}
        ), 500


@fc_bp.route("/modify", methods=["POST"])
def modify_fctask():
    try:
        # 获取请求参数
        form = request.form
        task_id = form.get("task_id", type=int)
        url = form.get("url")
        name = form.get("name")
        description = form.get("description")
        schedule = form.get("schedule")

        if not task_id:
            return jsonify({
                "success": False,
                "message": "缺少必要参数task_id"
            }), 400
            
        if not any([url, name, description, schedule]):
            return jsonify({
                "success": False,
                "message": "至少需要提供一个要修改的字段"
            }), 400

        # 调用database修改任务
        message = modify_task(
            task_id=task_id,
            url=url,
            name=name,
            description=description,
            schedule=schedule
        )

        return jsonify({
            "success": True,
            "message": message
        }), 200

    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"修改任务失败: {str(e)}"
        }), 500


@fc_bp.route("/info", methods=["GET"])
def get_task_status():
    """获取爬虫任务状态

    Query Parameters:
        fc_task_id: 爬虫任务ID

    Returns:
        JSON响应，包含任务状态信息
    """
    try:
        fc_task_id = request.args.get("fc_task_id")
        if not fc_task_id:
            return jsonify({"success": False, "message": "缺少任务ID参数"}), 400

        status = get_crawl_status(fc_task_id)
        return jsonify({"success": True, "data": status}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@fc_bp.route("/delete", methods=["POST"])
def delete_fctask():
    try:
        fc_task_id = request.form.get("fc_task_id")
        cancel_crawl_task(fc_task_id)
        return jsonify({"success": True, "message": "爬虫任务已取消"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

