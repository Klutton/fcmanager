from firecrawl import FirecrawlApp


def get_firecrawl_app(api_key: str = None, api_url: str = None):
    api_key = "" if not api_key else api_key
    api_url = "http://127.0.0.1:3002" if not api_url else api_url
    return FirecrawlApp(api_key=api_key, api_url=api_url)


def create_crawl_task(
    url: str, name: str = None, description: str = None, schedule: str = None
) -> dict:
    """
    创建新的爬虫任务

    Args:
        url: 目标网站URL
        name: 任务名称,可选
        description: 任务描述,可选
        schedule: 定时计划(cron表达式),可选

    Returns:
        dict: 包含任务ID等信息的字典

    Raises:
        Exception: 创建任务失败时抛出异常
    """
    try:
        app = get_firecrawl_app()

        # 构建任务参数
        task_params = {
            "url": url,
        }

        # 过滤掉None值
        task_params = {k: v for k, v in task_params.items() if v is not None}

        return app.async_crawl_url(**task_params)

    except Exception as e:
        raise Exception(f"创建爬虫任务失败: {str(e)}")


def get_crawl_status(task_id: str) -> dict:
    """
    根据任务ID查询爬虫任务状态

    Args:
        task_id: 爬虫任务ID

    Returns:
        dict: 包含任务状态信息的字典

    Raises:
        Exception: 查询状态失败时抛出异常
    """
    try:
        return get_firecrawl_app().check_crawl_status(task_id)

    except Exception as e:
        raise Exception(f"查询爬虫任务状态失败: {str(e)}")


def cancel_crawl_task(task_id: str) -> dict:
    """
    取消爬虫任务
    
    Args:
        task_id: 爬虫任务ID
    
    Returns:
        dict: 包含任务状态信息的字典
    """
    return get_firecrawl_app().cancel_crawl(task_id)


