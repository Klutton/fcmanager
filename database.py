from psycopg2 import Error, connect
from datetime import datetime, timedelta
import bcrypt
import schedule
import time
from fcmanager import create_crawl_task


class DatabaseError(Exception):
    """数据库操作相关的自定义异常"""
    pass


def get_database_connection():
    try:
        connection = connect(
            user="postgres",
            password="P@ssword0",
            host="127.0.0.1",
            port="5432",
            database="fcmanager",
        )
        return connection
    except Exception as error:
        print("连接PostgreSQL时发生错误:", error)
        return None


def init_database():
    # 连接到PostgreSQL数据库
    with get_database_connection() as connection:
        if connection is None:
            print("无法连接到数据库")
            exit(-1)

        # 创建cursor以执行数据库操作
        cursor = connection.cursor()

        # 创建account表
        create_account_table = """
            CREATE TABLE IF NOT EXISTS account (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
                role VARCHAR(20) NOT NULL DEFAULT 'user',  -- user, admin
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                approved_by INTEGER REFERENCES account(id),
                CONSTRAINT valid_status CHECK (status IN ('pending', 'approved', 'rejected')),
                CONSTRAINT valid_role CHECK (role IN ('user', 'admin'))
            );
        """

        # 创建profile表
        create_profile_table = """
            CREATE TABLE IF NOT EXISTS profile (
                user_id INTEGER REFERENCES account(id) PRIMARY KEY,
                nickname VARCHAR(50),
                name VARCHAR(50),
                department VARCHAR(100),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """

        # 创建task表
        create_task_table = """
            CREATE TABLE IF NOT EXISTS task (
                id SERIAL PRIMARY KEY,
                applicant_id INTEGER REFERENCES account(id),
                reviewer_id INTEGER REFERENCES account(id),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                category VARCHAR(100),
                site_url VARCHAR(200),
                schedule VARCHAR(100),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                fc_task_id VARCHAR(100),
                CONSTRAINT valid_task_status CHECK (status IN ('pending', 'approved', 'rejected'))
            );
        """

        # 创建task相关的索引
        create_task_applicant_index = """
            CREATE INDEX IF NOT EXISTS idx_task_applicant 
            ON task(applicant_id);
        """

        create_task_reviewer_index = """
            CREATE INDEX IF NOT EXISTS idx_task_reviewer
            ON task(reviewer_id);
        """

        # 执行创建表的SQL语句
        cursor.execute(create_account_table)
        cursor.execute(create_profile_table)
        cursor.execute(create_task_table)
        cursor.execute(create_task_applicant_index)
        cursor.execute(create_task_reviewer_index)

        # 提交事务
        connection.commit()
        print("数据库初始化成功")


# region 用户管理
def create_user(username: str, password: str) -> str:
    """
    创建新用户

    Args:
        username: 用户名
        password: 密码

    Raises:
        ValueError: 当密码不符合要求或用户名已存在时
        DatabaseError: 数据库操作错误时

    Returns:
        str: 成功消息
    """
    # 检查密码复杂度
    if len(password) < 8:
        raise ValueError("密码长度必须大于8位")

    # has_upper = any(c.isupper() for c in password)
    # has_upper = any(c.isupper() for c in password)
    has_alpha = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    # has_special = any(not c.isalnum() for c in password)

    if not (has_alpha and has_digit):
        raise ValueError("密码必须包含字母和数字")

    if not len(password) >= 8:
        raise ValueError("密码长度必须大于八位")

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 检查用户名是否已存在
                cursor.execute(
                    "SELECT id FROM account WHERE username = %s", (username,)
                )
                if cursor.fetchone():
                    raise ValueError("用户名已存在")

                # 使用bcrypt加密密码
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(password.encode(), salt)

                # 插入新用户
                cursor.execute(
                    """
                    INSERT INTO account (username, password)
                    VALUES (%s, %s)
                    """,
                    (username, hashed_password.decode()),
                )

                connection.commit()
                return "用户创建成功"

    except (Exception, Error) as error:
        raise DatabaseError(f"创建用户时发生错误: {str(error)}")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确

    Args:
        plain_password: 明文密码
        hashed_password: 数据库中存储的哈希密码

    Returns:
        bool: 密码是否匹配
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def login(username: str, password: str) -> tuple[int, str]:
    """
    用户登录

    Returns:
        tuple[int, str]: (用户ID, 消息)
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, password FROM account WHERE username = %s", (username,)
                )
                result = cursor.fetchone()

                if not result:
                    raise ValueError("用户名不存在")

                user_id, hashed_password = result

                if verify_password(password, hashed_password):
                    return user_id, "登录成功"
                else:
                    raise ValueError("密码错误")

    except (Exception, Error) as error:
        raise DatabaseError(f"登录时发生错误: {str(error)}")


def cleanup_pending_accounts(days: int = 7) -> int:
    """
    清理指定天数内未审核的账户及其关联数据

    Args:
        days: 待清理账户的天数阈值（默认7天）

    Returns:
        int: 清理的账户数量
    """
    if days < 0:
        return 0

    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 计算指定天数前的时间
                threshold_date = datetime.now() - timedelta(days=days)

                # 开始事务
                cursor.execute("BEGIN")

                # 获取需要清理的账户ID
                cursor.execute(
                    """
                    SELECT id FROM account 
                    WHERE status = 'pending' 
                    AND created_at < %s
                """,
                    (threshold_date,),
                )

                pending_accounts = cursor.fetchall()

                for (account_id,) in pending_accounts:
                    # 删除关联的profile记录
                    cursor.execute(
                        "DELETE FROM profile WHERE user_id = %s", (account_id,)
                    )

                    # 删除关联的task记录
                    cursor.execute(
                        """
                        DELETE FROM task 
                        WHERE applicant_id = %s OR reviewer_id = %s
                    """,
                        (account_id, account_id),
                    )

                    # 删除account记录
                    cursor.execute("DELETE FROM account WHERE id = %s", (account_id,))

                # 提交事务
                cursor.execute("COMMIT")

                return len(pending_accounts)

    except (Exception, Error) as error:
        if connection:
            connection.rollback()
        print(f"清理过期账户时发生错误: {error}")
        return 0


def approve_account(account_id: int, admin_id: int) -> str:
    """
    审核用户账户

    Args:
        account_id: 待审核的账户ID
        admin_id: 管理员ID

    Returns:
        str: 成功消息

    Raises:
        Exception: 审核失败时抛出异常
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 检查账户是否存在且状态为pending
                cursor.execute(
                    """
                    SELECT status FROM account 
                    WHERE id = %s
                """,
                    (account_id,),
                )

                result = cursor.fetchone()
                if not result:
                    raise Exception("账户不存在")

                if result[0] != "pending":
                    raise Exception("该账户已经被审核过")

                # 更新账户状态
                cursor.execute(
                    """
                    UPDATE account 
                    SET status = 'approved',
                        approved_at = CURRENT_TIMESTAMP,
                        approved_by = %s
                    WHERE id = %s
                """,
                    (admin_id, account_id),
                )

                connection.commit()
                return "审核通过"

    except (Exception, Error) as error:
        raise Exception(f"审核账户时发生错误: {str(error)}")


def reject_account(account_id: int, admin_id: int, reason: str = "") -> str:
    """
    拒绝用户账户

    Args:
        account_id: 待审核的账户ID
        admin_id: 管理员ID
        reason: 拒绝原因

    Returns:
        str: 成功消息

    Raises:
        Exception: 拒绝失败时抛出异常
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 更新账户状态为rejected
                cursor.execute(
                    """
                    UPDATE account 
                    SET status = 'rejected',
                        approved_at = CURRENT_TIMESTAMP,
                        approved_by = %s
                    WHERE id = %s AND status = 'pending'
                """,
                    (admin_id, account_id),
                )

                if cursor.rowcount == 0:
                    raise Exception("账户不存在或已经被审核")

                connection.commit()
                return "已拒绝该账户申请"

    except (Exception, Error) as error:
        raise Exception(f"拒绝账户时发生错误: {str(error)}")


def schedule_cleanup():
    schedule.every().day.at("00:00").do(cleanup_pending_accounts)

    while True:
        schedule.run_pending()
        time.sleep(3600)  # 每小时检查一次


def update_or_create_profile(
    user_id: int, nickname: str, name: str, department: str
) -> str:
    """
    更新或创建用户档案信息

    Args:
        user_id: 用户ID
        nickname: 昵称
        name: 姓名
        department: 部门

    Returns:
        str: 成功消息

    Raises:
        DatabaseError: 数据库操作错误时抛出
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 先检查记录是否存在
                cursor.execute(
                    f"""
                    INSERT INTO profile (user_id, nickname, name, department)
                    VALUES (%s, %s, %s, '{department}')
                    ON CONFLICT (user_id) 
                    DO UPDATE SET
                        nickname = EXCLUDED.nickname,
                        name = EXCLUDED.name,
                        department = '{department}',
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (user_id, nickname, name),
                )

                connection.commit()
                return "个人信息更新成功"

    except (Exception, Error) as error:
        raise DatabaseError(f"更新个人信息时发生错误: {str(error)}")

def get_profile(user_id: int, include_timestamps: bool = False) -> dict:
    """
    获取用户档案信息

    Args:
        user_id: 用户ID
        include_timestamps: 是否包含时间戳信息，默认为False

    Returns:
        dict: 包含用户档案信息的字典

    Raises:
        DatabaseError: 数据库操作错误时抛出
        ValueError: 用户档案不存在时抛出
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        p.nickname, 
                        p.name, 
                        p.department, 
                        p.created_at, 
                        p.updated_at,
                        a.role
                    FROM profile p
                    JOIN account a ON p.user_id = a.id 
                    WHERE p.user_id = %s
                    """,
                    (user_id,),
                )

                result = cursor.fetchone()
                if not result:
                    raise ValueError("用户档案不存在")

                profile = {
                    "nickname": result[0],
                    "name": result[1],
                    "department": result[2],
                    "role": result[5]
                }

                if include_timestamps:
                    profile.update({
                        "created_at": result[3],
                        "updated_at": result[4]
                    })

                return profile

    except ValueError as error:
        raise error
    except Exception as error:
        raise DatabaseError(f"获取用户档案时发生错误: {str(error)}")


def get_user_role(user_id: int) -> str:
    """
    获取用户角色

    Args:
        user_id: 用户ID

    Returns:
        str: 用户角色
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT role FROM account WHERE id = %s
                """,
                    (user_id,),
                )
                result = cursor.fetchone()
                if not result:
                    raise DatabaseError("用户不存在")
                return result[0]

    except Exception as error:
        raise DatabaseError(f"获取用户角色时发生错误: {str(error)}")


def get_username(user_id: int) -> str:
    """
    根据用户ID获取用户名
    
    Args:
        user_id: 用户ID
        
    Returns:
        str: 用户名
        
    Raises:
        ValueError: 用户不存在时抛出
        DatabaseError: 数据库操作错误时抛出
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT username FROM account WHERE id = %s",
                    (user_id,)
                )
                result = cursor.fetchone()
                if not result:
                    raise ValueError("用户不存在")
                return result[0]
                
    except Exception as error:
        raise DatabaseError(f"获取用户名时发生错误: {str(error)}")


# endregion


# region 任务管理
def create_task(
    applicant_id: int,
    name: str,
    description: str,
    category: str,
    site_url: str,
    status: str = "pending",
    reviewer_id: int = None,
    schedule: str = None,
    fc_task_id: str = None,
) -> str:
    """
    创建新任务

    Args:
        applicant_id: 申请人ID
        name: 任务名称
        description: 任务描述
        category: 任务类别
        site_url: 目标网站URL
        status: 任务状态，默认为'pending'
        reviewer_id: 审核人ID，默认为None
        schedule: 定时计划(cron表达式)，可选
        fc_task_id: 爬虫任务ID，可选

    Returns:
        str: 成功消息
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO task (
                        applicant_id, reviewer_id, name, description, 
                        category, site_url, schedule, status,
                        approved_at, fc_task_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        applicant_id,
                        reviewer_id,
                        name,
                        description,
                        category,
                        site_url,
                        schedule,
                        status,
                        datetime.now() if status == "approved" else None,
                        fc_task_id,
                    ),
                )

                task_id = cursor.fetchone()[0]
                connection.commit()

                return f"任务创建成功,ID:{task_id}"

    except Exception as error:
        raise DatabaseError(f"创建任务时发生错误: {str(error)}")


def modify_task(
    task_id: int,
    url: str = None,
    name: str = None,
    description: str = None,
    schedule: str = None,
) -> str:
    """
    修改任务信息，只允许修改pending或rejected状态的任务
    
    Args:
        task_id: 任务ID
        url: 新的目标网站URL,可选
        name: 新的任务名称,可选
        description: 新的任务描述,可选
        schedule: 新的定时计划,可选
        
    Returns:
        str: 成功消息
        
    Raises:
        DatabaseError: 数据库操作失败时抛出
        ValueError: 任务不存在或状态不允许修改时抛出
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 检查任务是否存在及其状态
                cursor.execute(
                    """
                    SELECT status FROM task WHERE id = %s
                """,
                    (task_id,)
                )
                task = cursor.fetchone()
                
                if not task:
                    raise ValueError("任务不存在")
                    
                if task[0] not in ["pending", "rejected"]:
                    raise ValueError("只能修改待审核或被拒绝的任务")
                
                # 构建更新语句
                update_fields = []
                params = []
                
                if url is not None:
                    update_fields.append("site_url = %s")
                    params.append(url)
                    
                if name is not None:
                    update_fields.append("name = %s")
                    params.append(name)
                    
                if description is not None:
                    update_fields.append("description = %s")
                    params.append(description)
                    
                if schedule is not None:
                    update_fields.append("schedule = %s")
                    params.append(schedule)
                    
                if not update_fields:
                    return "没有需要更新的内容"
                    
                # 执行更新
                query = f"""
                    UPDATE task 
                    SET {", ".join(update_fields)}
                    WHERE id = %s
                """
                params.append(task_id)
                
                cursor.execute(query, params)
                connection.commit()
                
                return "任务更新成功"
                
    except Exception as error:
        raise DatabaseError(f"修改任务时发生错误: {str(error)}")


def approve_task(task_id: int, admin_id: int, is_approved: bool = True) -> str:
    """
    审核任务并启动爬虫

    Args:
        task_id: 任务ID
        admin_id: 管理员ID
        is_approved: 是否通过审核,默认为True

    Returns:
        str: 成功消息
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 检查是否为管理员
                cursor.execute(
                    """
                    SELECT role FROM account WHERE id = %s
                """,
                    (admin_id,),
                )
                admin_role = cursor.fetchone()

                if not admin_role or admin_role[0] != "admin":
                    raise ValueError("只有管理员可以审核任务")

                # 获取任务信息
                cursor.execute(
                    """
                    SELECT status, site_url, name, description, schedule 
                    FROM task WHERE id = %s
                """,
                    (task_id,),
                )
                task = cursor.fetchone()

                if not task:
                    raise ValueError("任务不存在")

                if task[0] != "pending":
                    raise ValueError("该任务已经被审核")

                fc_task_id = None
                if is_approved:
                    # 创建爬虫任务，根据API文档修改参数
                    fc_response = create_crawl_task(
                        url=task[1],  # site_url
                    )
                    fc_task_id = fc_response.get("id")

                # 更新任务状态
                cursor.execute(
                    """
                    UPDATE task 
                    SET status = %s,
                        approved_at = CURRENT_TIMESTAMP,
                        reviewer_id = %s,
                        fc_task_id = %s
                    WHERE id = %s
                """,
                    (
                        "approved" if is_approved else "rejected",
                        admin_id,
                        fc_task_id,
                        task_id,
                    ),
                )

                connection.commit()
                return "任务审核通过并已启动爬虫" if is_approved else "任务审核未通过"

    except Exception as error:
        raise DatabaseError(f"审核任务时发生错误: {str(error)}")


def get_tasks(
    user_id: int = None,
    status: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    获取任务列表，支持多种过滤条件

    Args:
        user_id: 用户ID（可选，用于筛选特定用户的任务）
        status: 任务状态（可选，pending/approved/rejected）
        category: 任务类别（可选）
        start_date: 开始日期（可选，格式：YYYY-MM-DD）
        end_date: 结束日期（可选，格式：YYYY-MM-DD）
        page: 页码，默认1
        page_size: 每页数量，默认20

    Returns:
        dict: {
            'total': 总记录数,
            'total_pages': 总页数,
            'current_page': 当前页码,
            'tasks': [任务列表]
        }
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 构建基础查询
                query = """
                    SELECT 
                        t.id,
                        t.name,
                        t.description,
                        t.category,
                        t.site_url,
                        t.schedule,
                        t.status,
                        t.created_at,
                        t.approved_at,
                        t.fc_task_id,
                        a.username as applicant_name,
                        r.username as reviewer_name
                    FROM task t
                    LEFT JOIN account a ON t.applicant_id = a.id
                    LEFT JOIN account r ON t.reviewer_id = r.id
                    WHERE 1=1
                """
                params = []

                # 添加过滤条件
                if user_id:
                    query += " AND (t.applicant_id = %s OR t.reviewer_id = %s)"
                    params.extend([user_id, user_id])

                if status:
                    query += " AND t.status = %s"
                    params.append(status)

                if category:
                    query += " AND t.category = %s"
                    params.append(category)

                if start_date:
                    query += " AND t.created_at >= %s"
                    params.append(start_date)

                if end_date:
                    query += " AND t.created_at <= %s"
                    params.append(end_date)

                # 获取总记录数
                count_query = f"SELECT COUNT(*) FROM ({query}) AS count_query"
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]

                # 添加分页
                query += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
                offset = (page - 1) * page_size
                params.extend([page_size, offset])

                # 执行最终查询
                cursor.execute(query, params)
                tasks = []
                for row in cursor.fetchall():
                    tasks.append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "description": row[2],
                            "category": row[3],
                            "site_url": row[4],
                            "schedule": row[5],
                            "status": row[6],
                            "created_at": row[7].strftime("%Y-%m-%d %H:%M:%S"),
                            "approved_at": row[8].strftime("%Y-%m-%d %H:%M:%S")
                            if row[8]
                            else None,
                            "fc_task_id": row[9],
                            "applicant_name": row[10],
                            "reviewer_name": row[11],
                        }
                    )

                total_pages = (total_count + page_size - 1) // page_size

                return {
                    "total": total_count,
                    "total_pages": total_pages,
                    "current_page": page,
                    "tasks": tasks,
                }

    except Exception as error:
        raise DatabaseError(f"获取任务列表时发生错误: {str(error)}")


def delete_task(task_id: int) -> str:
    """
    根据任务ID删除任务记录

    Args:
        task_id: 要删除的任务ID

    Returns:
        str: 成功消息

    Raises:
        DatabaseError: 数据库操作失败时抛出
        ValueError: 任务不存在时抛出
    """
    try:
        with get_database_connection() as connection:
            with connection.cursor() as cursor:
                # 检查任务是否存在
                cursor.execute(
                    "SELECT id FROM task WHERE id = %s",
                    (task_id,)
                )
                if not cursor.fetchone():
                    raise ValueError("任务不存在")

                # 删除任务
                cursor.execute(
                    "DELETE FROM task WHERE id = %s",
                    (task_id,)
                )
                connection.commit()
                return "任务删除成功"

    except Exception as error:
        raise DatabaseError(f"删除任务时发生错误: {str(error)}")


# endregion

if __name__ == "__main__":
    init_database()
