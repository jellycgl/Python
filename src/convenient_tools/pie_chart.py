import math
import matplotlib.pyplot as plt

# 示例输入数据：分类及其对应的数值
data1 = {
    "New vendor/technology support": 50,
    "Improvements to existing vendor/tech support": 40,
    "Legacy issue and bug fixing": 5,
    "Supportive system new feature enhancement": 5,
    "Internal platform infrastructure development": 5
}

data2 = {
    "New vendor/technology development": 45,
    "Customer requirement expansion": 30,
    "Platform/Customer issue resolution": 25
}

data = data2

# 准备标签和数值
labels = list(data.keys())
sizes = list(data.values())

# 创建图像窗口（调整图像尺寸以显示长标签）
fig, ax = plt.subplots(figsize=(10, 8))

# 绘制饼图（仅显示百分比）
wedges, texts, autotexts = ax.pie(
    sizes,
    labels=None,                   # 不在图上显示 label
    autopct='%1.1f%%',             # 显示百分比
    startangle=140,
    textprops={'fontsize': 10}
)

# # 为每个 wedge 添加标签，放在百分比下方（手动定位）
# for i, (wedge, label) in enumerate(zip(wedges, labels)):
#     angle = (wedge.theta2 + wedge.theta1) / 2
#     x = 0.7 * math.cos(math.radians(angle))
#     y = 0.7 * math.sin(math.radians(angle)) - 0.1  # 往下偏移一点放 label

#     ax.text(
#         x, y,
#         label,
#         ha='center',
#         va='top',
#         fontsize=9,
#         wrap=True
#     )

# 添加标题
ax.set_title("System Resource Allocation")

# 自动调整图形边距，防止内容被裁剪
plt.tight_layout()

# 保存图像
output_path = "pie_chart_label_below_percent.png"
plt.savefig(output_path, bbox_inches='tight')

# 可选：提示保存位置
print(f"✅ 饼图已保存到: {output_path}")
