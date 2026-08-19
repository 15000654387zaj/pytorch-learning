import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
import argparse

# 尝试导入 websocket，如果没有安装则降级使用 HTTP 轮询模式
HAS_WEBSOCKET = False
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class ComfyUIClient:
    """ComfyUI API 客户端，负责发送 Workflow 请求并自动监听与下载高清处理后的图片"""

    def __init__(self, server_address="127.0.0.1:8188", output_dir="./output"):
        self.server_address = server_address.rstrip('/')
        self.output_dir = output_dir
        self.client_id = str(uuid.uuid4())
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def upload_image(self, image_path):
        """将本地图片 (如 '0风格和.jpg') 上传到 ComfyUI 的 input 目录"""
        if not os.path.exists(image_path):
            print(f"[警告] 未找到本地图片文件: {image_path}")
            return os.path.basename(image_path)

        filename = os.path.basename(image_path)
        url = f"http://{self.server_address}/upload/image"
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

        print(f"[上传] 正在上传图片 '{filename}' 到 ComfyUI 服务端...")
        with open(image_path, "rb") as f:
            file_bytes = f.read()

        # 构建 multipart/form-data 报文
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + file_bytes + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
            f"true\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                uploaded_name = data.get("name", filename)
                print(f"[成功] 图片 '{uploaded_name}' 已就绪！")
                return uploaded_name
        except Exception as e:
            print(f"[提示] 上传图片到 ComfyUI 出现提示 ({e})，尝试直接使用文件名 '{filename}'。")
            return filename

    def load_and_convert_workflow(self, workflow_path, target_image="0风格和.jpg"):
        """读取工作流 JSON 并自动转换为 ComfyUI API /prompt 所需格式，更新目标图片"""
        if not os.path.exists(workflow_path):
            raise FileNotFoundError(f"未找到工作流文件: {workflow_path}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            wf_data = json.load(f)

        # 判断是 ComfyUI 前端 UI 图形格式还是 API 格式
        if "nodes" in wf_data and isinstance(wf_data["nodes"], list):
            print(f"[转换] 解析前端 UI 格式工作流 '{workflow_path}' 为 API 提交格式...")
            api_prompt = {}
            links = {link[0]: (str(link[1]), link[2]) for link in wf_data.get("links", []) if link}

            for node in wf_data.get("nodes", []):
                # 忽略禁用的节点 (mode != 0)
                if node.get("mode", 0) != 0:
                    continue

                node_id = str(node["id"])
                node_type = node["type"]
                node_inputs = {}

                # 映射节点间连接
                for input_info in node.get("inputs", []):
                    link_id = input_info.get("link")
                    input_name = input_info.get("name")
                    if link_id is not None and link_id in links:
                        node_inputs[input_name] = [links[link_id][0], links[link_id][1]]

                # 映射控件参数
                widgets_values = node.get("widgets_values", [])
                if node_type == "LoadImage":
                    node_inputs["image"] = target_image
                elif node_type == "RTXVideoSuperResolution":
                    if isinstance(widgets_values, list) and len(widgets_values) >= 3:
                        node_inputs["resize_type"] = widgets_values[0]
                        node_inputs["scale"] = widgets_values[1]
                        node_inputs["quality"] = widgets_values[2]
                    elif isinstance(widgets_values, dict):
                        node_inputs.update(widgets_values)
                elif node_type == "SaveImage":
                    prefix = "RTX_Upscale"
                    if isinstance(widgets_values, list) and len(widgets_values) > 0 and widgets_values[0]:
                        prefix = widgets_values[0]
                    elif isinstance(widgets_values, dict) and "filename_prefix" in widgets_values:
                        prefix = widgets_values["filename_prefix"]
                    node_inputs["filename_prefix"] = prefix

                api_prompt[node_id] = {
                    "inputs": node_inputs,
                    "class_type": node_type
                }
            return api_prompt
        else:
            # 已经是 API 格式，更新 LoadImage 的图片
            print(f"[加载] 加载 API 格式工作流 '{workflow_path}'...")
            for node_id, node in wf_data.items():
                if isinstance(node, dict) and node.get("class_type") == "LoadImage":
                    if "inputs" in node:
                        node["inputs"]["image"] = target_image
            return wf_data

    def queue_prompt(self, prompt_workflow):
        """向 ComfyUI /prompt 发送 POST 请求提交任务"""
        url = f"http://{self.server_address}/prompt"
        payload = {
            "prompt": prompt_workflow,
            "client_id": self.client_id
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                prompt_id = resp_data.get("prompt_id")
                print(f"[成功] 图片清晰化任务已提交给 ComfyUI，Prompt ID: {prompt_id}")
                return prompt_id
        except urllib.error.URLError as e:
            print(f"[错误] 无法连接到 ComfyUI 服务 ({url}): {e}")
            print("请确认 ComfyUI 是否已启动，且监听端口为 8188。")
            sys.exit(1)

    def track_by_websocket(self, prompt_id, timeout=300):
        """通过 WebSocket 实时监听任务执行进度"""
        ws_url = f"ws://{self.server_address}/ws?client_id={self.client_id}"
        print(f"[通信] 正在建立 WebSocket 连接: {ws_url}")
        
        ws = websocket.WebSocket()
        try:
            ws.connect(ws_url)
        except Exception as e:
            print(f"[警告] WebSocket 连接失败 ({e})，降级为 HTTP 轮询模式...")
            return False

        start_time = time.time()
        print("[监听] 开始接收 ComfyUI 超分/清晰化计算进度...")
        
        try:
            while True:
                if time.time() - start_time > timeout:
                    print("[超时] 等待生成超时！")
                    ws.close()
                    return False

                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    msg_type = message.get("type")
                    data = message.get("data", {})

                    if msg_type == "status":
                        exec_info = data.get("status", {}).get("exec_info", {})
                        queue_remaining = exec_info.get("queue_remaining", 0)
                        print(f"[状态] 队列剩余任务数: {queue_remaining}")

                    elif msg_type == "executing":
                        node = data.get("node")
                        msg_prompt_id = data.get("prompt_id")
                        if msg_prompt_id == prompt_id:
                            if node is None:
                                print("[完成] 所有节点清晰化计算完成！")
                                ws.close()
                                return True
                            else:
                                print(f"[进度] 正在执行节点: {node}")

                    elif msg_type == "execution_error":
                        print(f"[错误] 节点执行报错: {data}")
                        ws.close()
                        return False
        except Exception as e:
            print(f"[警告] WebSocket 监听中断 ({e})，切换为 HTTP 轮询模式...")
            try:
                ws.close()
            except Exception:
                pass
            return False

    def track_by_polling(self, prompt_id, timeout=300, poll_interval=1.0):
        """通过 HTTP 轮询监听任务完成"""
        print(f"[监听] 通过 HTTP 轮询监听任务 {prompt_id} 进度...")
        history_url = f"http://{self.server_address}/history/{prompt_id}"
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                print("[超时] 等待生成超时！")
                return False

            try:
                req = urllib.request.Request(history_url)
                with urllib.request.urlopen(req) as response:
                    history = json.loads(response.read().decode("utf-8"))
                    if prompt_id in history:
                        print("[完成] 任务在 ComfyUI 中清晰化处理完毕！")
                        return True
            except urllib.error.URLError:
                pass

            time.sleep(poll_interval)

    def get_history(self, prompt_id):
        """获取生成历史数据"""
        history_url = f"http://{self.server_address}/history/{prompt_id}"
        req = urllib.request.Request(history_url)
        with urllib.request.urlopen(req) as response:
            history = json.loads(response.read().decode("utf-8"))
            return history.get(prompt_id, {})

    def download_images(self, prompt_id):
        """从历史记录中解析超分处理后的结果并下载保存到本地"""
        history = self.get_history(prompt_id)
        outputs = history.get("outputs", {})
        
        saved_files = []

        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img_info in node_output["images"]:
                    filename = img_info.get("filename")
                    subfolder = img_info.get("subfolder", "")
                    img_type = img_info.get("type", "output")

                    params = urllib.parse.urlencode({
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": img_type
                    })
                    image_url = f"http://{self.server_address}/view?{params}"
                    
                    save_path = os.path.join(self.output_dir, filename)
                    if os.path.exists(save_path):
                        name, ext = os.path.splitext(filename)
                        timestamp = int(time.time())
                        save_path = os.path.join(self.output_dir, f"{name}_{timestamp}{ext}")

                    print(f"[下载] 正在下载清晰化图片 ({filename}) -> {save_path}")
                    
                    try:
                        with urllib.request.urlopen(image_url) as resp, open(save_path, "wb") as out_file:
                            out_file.write(resp.read())
                        saved_files.append(save_path)
                    except Exception as e:
                        print(f"[错误] 下载图片 {filename} 失败: {e}")

        if saved_files:
            print(f"\n[成功] 所有清晰化处理后的图片已保存至: {os.path.abspath(self.output_dir)}")
            for file_path in saved_files:
                print(f"  - {file_path}")
        else:
            print("[提醒] 历史记录中未获取到输出图片，请检查工作流中是否包含 SaveImage 节点。")

        return saved_files

    def run(self, workflow_path="rtx_workflow.json", image_path="0风格和.jpg", timeout=300, poll_interval=1.0):
        """完整运行流程"""
        # 1. 上传图片到 ComfyUI 目录
        uploaded_image_name = self.upload_image(image_path)

        # 2. 读取并转换工作流 JSON
        prompt_workflow = self.load_and_convert_workflow(workflow_path, target_image=uploaded_image_name)

        # 3. 发送 POST 请求提交生成任务
        prompt_id = self.queue_prompt(prompt_workflow)

        # 4. 监听生成进度
        success = False
        if HAS_WEBSOCKET:
            success = self.track_by_websocket(prompt_id, timeout=timeout)
        
        if not success:
            success = self.track_by_polling(prompt_id, timeout=timeout, poll_interval=poll_interval)

        # 5. 下载生成结果
        if success:
            return self.download_images(prompt_id)
        else:
            print("[失败] 清晰化生成任务处理失败。")
            return []


def main():
    parser = argparse.ArgumentParser(description="ComfyUI RTX图片超分/清晰化 自动化调用与下载脚本")
    parser.add_argument("--workflow", type=str, default="rtx_workflow.json", help="工作流 JSON 文件路径 (默认: rtx_workflow.json)")
    parser.add_argument("--image", type=str, default="0风格和.jpg", help="需要清晰化的图片路径 (默认: 0风格和.jpg)")
    parser.add_argument("--server", type=str, default="127.0.0.1:8188", help="ComfyUI 服务地址 (默认: 127.0.0.1:8188)")
    parser.add_argument("--output-dir", type=str, default="./output", help="高清图片保存目录 (默认: ./output)")
    parser.add_argument("--timeout", type=int, default=300, help="生成任务等待超时时间（秒） (默认: 300)")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="轮询间隔秒数 (默认: 1.0)")

    args = parser.parse_args()

    client = ComfyUIClient(server_address=args.server, output_dir=args.output_dir)
    client.run(workflow_path=args.workflow, image_path=args.image, timeout=args.timeout, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
