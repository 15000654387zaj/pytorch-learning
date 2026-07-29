import torch

print("====================================")
print("1. PyTorch 版本:", torch.__version__)
print("2. CUDA(显卡驱动) 是否可用:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("3. 当前使用的显卡名称:", torch.cuda.get_device_name(0))
else:
    print("3. ❌ 显卡不可用，请检查驱动")
print("====================================")