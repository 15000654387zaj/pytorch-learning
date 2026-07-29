import torch
import time

print("-" * 30)
print("【AI辅助编程 实验室环境测试】")
print("-" * 30)

# 1. 基础环境检查
print(f"Python 版本: {torch.__version__}")
print(f"CUDA 是否可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    # 2. 显卡信息
    device_id = torch.cuda.current_device()
    gpu_name = torch.cuda.get_device_name(device_id)
    print(f"检测到显卡: {gpu_name}")
    
    # 3. 显存压力测试（模拟数字人推理）
    print("\n正在进行显存压力测试...")
    try:
        # 在 4070 上创建一个巨大的随机矩阵
        start_time = time.time()
        x = torch.randn(10000, 10000).cuda()
        y = torch.randn(10000, 10000).cuda()
        
        # 做一个矩阵乘法（4070 的拿手好戏）
        z = torch.matmul(x, y)
        
        end_time = time.time()
        print(f"计算完成！耗时: {end_time - start_time:.4f} 秒")
        print(f"测试结果: 你的 {gpu_name} 动力澎湃，环境配置完美！")
        
    except Exception as e:
        print(f"计算过程中出错: {e}")
else:
    print("警告: 虽然 Python 跑通了，但没有检测到 CUDA！")
    print("你需要安装 GPU 版本的 PyTorch，而不是 CPU 版。")
    print("安装命令: conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia")

print("-" * 30)