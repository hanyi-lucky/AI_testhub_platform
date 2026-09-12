"""
WebSocket 请求执行模块。

此前项目中 WebSocket 仅作为数据模型的分类枚举存在，没有真正的执行逻辑，
所有请求都被当作 HTTP 走 requests.request()。本模块用同步的 websocket-client
库补齐 WS 的真实执行：建立连接 → 发送消息 → 接收响应 → 超时控制。
"""
import time


def execute_websocket_request(url, message=None, headers=None, timeout=10, recv_count=1):
    """执行一次 WebSocket 请求。

    参数:
        url: ws:// 或 wss:// 地址
        message: 连接后要发送的文本消息（可为 None，仅接收）
        headers: 建立连接时携带的 HTTP 头（dict）
        timeout: 连接与单次接收的超时时间（秒）
        recv_count: 期望接收的消息条数

    返回 dict:
        {
          'success': bool,
          'response': 首条响应文本,
          'messages': [接收到的所有消息],
          'response_time': 毫秒,
          'error': 错误信息（成功时为空）,
        }
    """
    result = {
        'success': False,
        'response': None,
        'messages': [],
        'response_time': None,
        'error': '',
    }

    try:
        # 延迟导入，避免未安装该依赖时影响整个模块加载
        import websocket  # websocket-client
    except ImportError:
        result['error'] = '缺少依赖 websocket-client，请执行 pip install websocket-client'
        return result

    # 归一化 URL 协议
    if url.startswith('http://'):
        url = 'ws://' + url[len('http://'):]
    elif url.startswith('https://'):
        url = 'wss://' + url[len('https://'):]

    header_list = [f"{k}: {v}" for k, v in (headers or {}).items()]

    ws = None
    start = time.time()
    try:
        ws = websocket.create_connection(url, timeout=timeout, header=header_list)
        if message is not None:
            ws.send(message)

        for _ in range(max(1, recv_count)):
            try:
                msg = ws.recv()
                result['messages'].append(msg)
            except Exception:
                break

        result['response'] = result['messages'][0] if result['messages'] else None
        result['success'] = True
    except Exception as e:
        result['error'] = str(e)
    finally:
        result['response_time'] = (time.time() - start) * 1000
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    return result
