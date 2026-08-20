import os
import sys
import json
import time
import uuid
import random
import argparse
import urllib.request
import urllib.parse
import urllib.error

# 确保 Windows 终端支持 UTF-8 打印输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 尝试导入 websocket，用于实时接收执行状态与进度反馈
HAS_WEBSOCKET = False
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False




class ComfyNodeMetaParser:
    """负责读取并解析 comfy_nodes_meta.json 节点元数据"""

    def __init__(self, meta_path="comfy_nodes_meta.json"):
        self.meta_path = meta_path
        self.meta = self._load_meta()

    def _load_meta(self):
        if not os.path.exists(self.meta_path):
            print(f"[警告] 未在路径 '{self.meta_path}' 找到节点元数据文件，将使用默认标准参数。")
            return {}
        try:
            with open(self.meta_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                print(f"[元数据] 成功加载 {self.meta_path}，包含 {len(data)} 个节点定义。")
                return data
        except Exception as e:
            print(f"[警告] 读取节点元数据失败 ({e})，使用默认配置。")
            return {}

    def get_node_meta(self, node_name):
        return self.meta.get(node_name, {})

    def get_available_checkpoints(self):
        """从 CheckpointLoaderSimple 元数据中提取可用模型列表"""
        ckpt_meta = self.get_node_meta("CheckpointLoaderSimple")
        try:
            req = ckpt_meta.get("input", {}).get("required", {})
            ckpt_options = req.get("ckpt_name", [[]])[0]
            if isinstance(ckpt_options, list) and len(ckpt_options) > 0:
                return ckpt_options
        except Exception:
            pass
        return ["v1-5-pruned-emaonly-fp16.safetensors"]

    def get_available_samplers(self):
        """从 KSampler 元数据中提取可用采样器列表"""
        ksampler_meta = self.get_node_meta("KSampler")
        try:
            req = ksampler_meta.get("input", {}).get("required", {})
            sampler_options = req.get("sampler_name", [[]])[0]
            if isinstance(sampler_options, list) and len(sampler_options) > 0:
                return sampler_options
        except Exception:
            pass
        return ["euler", "dpmpp_2m", "ddim"]

    def get_available_schedulers(self):
        """从 KSampler 元数据中提取可用调度器列表"""
        ksampler_meta = self.get_node_meta("KSampler")
        try:
            req = ksampler_meta.get("input", {}).get("required", {})
            scheduler_options = req.get("scheduler", [[]])[0]
            if isinstance(scheduler_options, list) and len(scheduler_options) > 0:
                return scheduler_options
        except Exception:
            pass
        return ["normal", "karras", "simple"]


class ComfyWorkflowBuilder:
    """根据 comfy_nodes_meta.json 元数据自动拼接标准 ComfyUI txt2img 工作流 API JSON"""

    def __init__(self, meta_parser: ComfyNodeMetaParser):
        self.meta_parser = meta_parser

    def build_txt2img_workflow(
        self,
        prompt: str,
        negative_prompt: str = "bad quality, blurry, text, watermark, deformed, lowres",
        width: int = 512,
        height: int = 512,
        ckpt_name: str = None,
        seed: int = None,
        steps: int = 20,
        cfg: float = 8.0,
        sampler_name: str = "euler",
        scheduler: str = "normal",
        filename_prefix: str = "AutoComfyUI"
    ) -> dict:
        """构建标准 Text-to-Image 工作流 (模型加载 -> 提示词编码 -> 采样器 -> VAE解码 -> 保存图片)"""
        # 1. 确定 Checkpoint 模型
        available_ckpts = self.meta_parser.get_available_checkpoints()
        if not ckpt_name:
            ckpt_name = available_ckpts[0] if available_ckpts else "v1-5-pruned-emaonly-fp16.safetensors"
        elif ckpt_name not in available_ckpts and available_ckpts:
            print(f"[提示] 模型 '{ckpt_name}' 可能未在元数据中列出，仍将尝试使用。")

        # 2. 确定随机种子
        if seed is None or seed < 0:
            seed = random.randint(1, 18446744073709551615)

        # 3. 按照标准节点关系拼接 API JSON
        # Node 1: CheckpointLoaderSimple (输出: 0:MODEL, 1:CLIP, 2:VAE)
        # Node 2: EmptyLatentImage (输出: 0:LATENT)
        # Node 3: CLIPTextEncode (正向提示词, 输出: 0:CONDITIONING)
        # Node 4: CLIPTextEncode (反向提示词, 输出: 0:CONDITIONING)
        # Node 5: KSampler (输出: 0:LATENT)
        # Node 6: VAEDecode (输出: 0:IMAGE)
        # Node 7: SaveImage (保存图片)

        workflow = {
            "1": {
                "inputs": {
                    "ckpt_name": ckpt_name
                },
                "class_type": "CheckpointLoaderSimple",
                "_meta": {
                    "title": "Load Checkpoint"
                }
            },
            "2": {
                "inputs": {
                    "width": int(width),
                    "height": int(height),
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage",
                "_meta": {
                    "title": "Empty Latent Image"
                }
            },
            "3": {
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 1]
                },
                "class_type": "CLIPTextEncode",
                "_meta": {
                    "title": "CLIP Text Encode (Positive Prompt)"
                }
            },
            "4": {
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["1", 1]
                },
                "class_type": "CLIPTextEncode",
                "_meta": {
                    "title": "CLIP Text Encode (Negative Prompt)"
                }
            },
            "5": {
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["2", 0],
                    "seed": seed,
                    "steps": int(steps),
                    "cfg": float(cfg),
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0
                },
                "class_type": "KSampler",
                "_meta": {
                    "title": "KSampler"
                }
            },
            "6": {
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2]
                },
                "class_type": "VAEDecode",
                "_meta": {
                    "title": "VAE Decode"
                }
            },
            "7": {
                "inputs": {
                    "images": ["6", 0],
                    "filename_prefix": filename_prefix
                },
                "class_type": "SaveImage",
                "_meta": {
                    "title": "Save Image"
                }
            }
        }

        return workflow


class ComfyUIClient:
    """ComfyUI API 客户端，负责请求分发、状态监听与图片下载"""

    def __init__(self, server_address="127.0.0.1:8188", output_dir="./output"):
        self.server_address = server_address.rstrip('/')
        self.output_dir = output_dir
        self.client_id = str(uuid.uuid4())

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def queue_prompt(self, workflow: dict) -> str:
        """向 ComfyUI /prompt 接口提交生成任务"""
        url = f"http://{self.server_address}/prompt"
        payload = {
            "prompt": workflow,
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
                print(f"[提交成功] 任务已发送至 ComfyUI 服务，Prompt ID: {prompt_id}")
                return prompt_id
        except urllib.error.URLError as e:
            print(f"[错误] 无法连接到 ComfyUI 服务 ({url}): {e}")
            print("请确认 ComfyUI 服务是否已在本地启动 (http://127.0.0.1:8188)。")
            sys.exit(1)

    def track_by_websocket(self, prompt_id: str, timeout: int = 300) -> bool:
        """通过 WebSocket 实时监听渲染进度"""
        ws_url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
        print(f"[通信] 正在连接 WebSocket: {ws_url}")

        try:
            ws = websocket.WebSocket()
            ws.connect(ws_url)
        except Exception as e:
            print(f"[提示] WebSocket 连接未就绪 ({e})，将切换至 HTTP 轮询模式。")
            return False

        start_time = time.time()
        print("[监听] 开始实时接收渲染状态...")

        try:
            while True:
                if time.time() - start_time > timeout:
                    print("[超时] 等待渲染超时！")
                    ws.close()
                    return False

                msg = ws.recv()
                if isinstance(msg, str):
                    message = json.loads(msg)
                    msg_type = message.get("type")
                    data = message.get("data", {})

                    if msg_type == "status":
                        exec_info = data.get("status", {}).get("exec_info", {})
                        queue_remaining = exec_info.get("queue_remaining", 0)
                        if queue_remaining > 0:
                            print(f"[队列状态] 等待中，队列剩余任务数: {queue_remaining}")

                    elif msg_type == "progress":
                        value = data.get("value", 0)
                        max_val = data.get("max", 0)
                        print(f"[采样进度] Step {value}/{max_val} ({int(value/max_val*100) if max_val else 0}%)")

                    elif msg_type == "executing":
                        node = data.get("node")
                        msg_prompt_id = data.get("prompt_id")
                        if msg_prompt_id == prompt_id:
                            if node is None:
                                print("[完成] 所有节点计算渲染完成！")
                                ws.close()
                                return True
                            else:
                                print(f"[执行节点] 当前执行节点 ID: {node}")

                    elif msg_type == "execution_error":
                        print(f"[错误] 节点执行异常: {data}")
                        ws.close()
                        return False
        except Exception as e:
            print(f"[提示] WebSocket 连接断开 ({e})，自动切换至 HTTP 轮询模式。")
            try:
                ws.close()
            except Exception:
                pass
            return False

    def track_by_polling(self, prompt_id: str, timeout: int = 300, poll_interval: float = 1.0) -> bool:
        """通过 HTTP 轮询查询 /history/{prompt_id} 监听渲染状态"""
        print(f"[监听] 使用 HTTP 轮询监听任务 {prompt_id}...")
        history_url = f"http://{self.server_address}/history/{prompt_id}"
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                print("[超时] 等待渲染超时！")
                return False

            try:
                req = urllib.request.Request(history_url)
                with urllib.request.urlopen(req) as response:
                    history = json.loads(response.read().decode("utf-8"))
                    if prompt_id in history:
                        print("[完成] 任务在 ComfyUI 中渲染完成！")
                        return True
            except urllib.error.URLError:
                pass

            time.sleep(poll_interval)

    def get_history(self, prompt_id: str) -> dict:
        """从 /history 接口获取任务执行输出"""
        history_url = f"http://{self.server_address}/history/{prompt_id}"
        req = urllib.request.Request(history_url)
        with urllib.request.urlopen(req) as response:
            history = json.loads(response.read().decode("utf-8"))
            return history.get(prompt_id, {})

    def download_images(self, prompt_id: str) -> list:
        """解析生成结果，下载图片并保存至 ./output 目录"""
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

                    print(f"[下载] 正在保存图片 ({filename}) -> {save_path}")

                    try:
                        with urllib.request.urlopen(image_url) as resp, open(save_path, "wb") as out_file:
                            out_file.write(resp.read())
                        saved_files.append(save_path)
                    except Exception as e:
                        print(f"[错误] 下载图片 {filename} 失败: {e}")

        if saved_files:
            print(f"\n✨ 生成成功！所有图片已保存至: {os.path.abspath(self.output_dir)}")
            for p in saved_files:
                print(f"   📂 {p}")
        else:
            print("[警告] 未在历史记录中找到生成的图片。")

        return saved_files

    def run(self, workflow: dict, timeout: int = 300, poll_interval: float = 1.0) -> list:
        """执行完整生成与下载工作流"""
        prompt_id = self.queue_prompt(workflow)

        success = False
        if HAS_WEBSOCKET:
            success = self.track_by_websocket(prompt_id, timeout=timeout)

        if not success:
            success = self.track_by_polling(prompt_id, timeout=timeout, poll_interval=poll_interval)

        if success:
            return self.download_images(prompt_id)
        else:
            print("[失败] 任务未能正常完成。")
            return []


def parse_args():
    parser = argparse.ArgumentParser(
        description="ComfyUI 自动化文生图 (Text-to-Image) 生成脚本",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # 核心需求参数
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="a beautiful anime girl with glowing eyes, cybernetic style, highly detailed, master piece, 8k wallpaper",
        help="正向提示词 (Positive Prompt)"
    )
    parser.add_argument(
        "--width", "-W",
        type=int,
        default=512,
        help="生成图片宽度 (Width)"
    )
    parser.add_argument(
        "--height", "-H",
        type=int,
        default=512,
        help="生成图片高度 (Height)"
    )

    # 扩展生成参数
    parser.add_argument(
        "--negative-prompt", "-np",
        type=str,
        default="bad anatomy, blurry, low quality, distorted, watermark, text",
        help="反向提示词 (Negative Prompt)"
    )
    parser.add_argument(
        "--ckpt", "--model",
        type=str,
        default=None,
        help="Checkpoint 模型名称 (默认自动读取 comfy_nodes_meta.json 中的首选模型)"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=20,
        help="采样步数 (Steps)"
    )
    parser.add_argument(
        "--cfg",
        type=float,
        default=8.0,
        help="CFG Scale 提示词引导系数"
    )
    parser.add_argument(
        "--sampler",
        type=str,
        default="euler",
        help="采样器算法 (Sampler Name)"
    )
    parser.add_argument(
        "--scheduler",
        type=str,
        default="normal",
        help="调度器 (Scheduler)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="随机种子 (默认 -1 表示随机生成)"
    )

    # 服务与路径设置
    parser.add_argument(
        "--server",
        type=str,
        default="127.0.0.1:8188",
        help="ComfyUI 服务地址"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="输出图片保存目录"
    )
    parser.add_argument(
        "--meta-file",
        type=str,
        default="comfy_nodes_meta.json",
        help="ComfyUI 节点元数据文件路径"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅生成并打印工作流 JSON，不向服务端发送请求"
    )
    parser.add_argument(
        "--save-workflow-json",
        type=str,
        default=None,
        help="可选：将生成的 API JSON 工作流保存到指定文件"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("🚀 ComfyUI 自动化文生图主程序 (Auto Generate)")
    print("=" * 60)
    print(f"📝 提示词 (Prompt): {args.prompt}")
    print(f"🚫 反向词 (Negative): {args.negative_prompt}")
    print(f"📐 分辨率: {args.width}x{args.height}")
    print(f"⚙️ 采样配置: Steps={args.steps}, CFG={args.cfg}, Sampler={args.sampler}, Scheduler={args.scheduler}")

    # 1. 解析节点元数据
    meta_parser = ComfyNodeMetaParser(meta_path=args.meta_file)

    # 2. 自动拼接工作流 JSON
    builder = ComfyWorkflowBuilder(meta_parser=meta_parser)
    workflow = builder.build_txt2img_workflow(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        width=args.width,
        height=args.height,
        ckpt_name=args.ckpt,
        seed=args.seed if args.seed >= 0 else None,
        steps=args.steps,
        cfg=args.cfg,
        sampler_name=args.sampler,
        scheduler=args.scheduler,
        filename_prefix="AutoComfyUI"
    )

    # 可选保存工作流 JSON 文件
    if args.save_workflow_json:
        with open(args.save_workflow_json, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        print(f"[保存] 工作流 API JSON 已保存至: {args.save_workflow_json}")

    # 若为 dry-run 模式，打印 JSON 并退出
    if args.dry_run:
        print("\n[Dry Run] 生成的 ComfyUI API JSON 工作流如下:")
        print(json.dumps(workflow, indent=2, ensure_ascii=False))
        return

    # 3. 提交任务至 ComfyUI 服务并监听下载
    client = ComfyUIClient(server_address=args.server, output_dir=args.output_dir)
    client.run(workflow)


if __name__ == "__main__":
    main()
