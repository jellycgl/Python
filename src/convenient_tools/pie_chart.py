import matplotlib.pyplot as plt

# 示例输入数据：分类及其对应的数值
data = {
    "Network": 35,
    "Storage": 25,
    "Compute": 20,
    "Security": 10,
    "Backup": 10
}

# 提取标签和对应数值
labels = list(data.keys())
sizes = list(data.values())

# 创建图形窗口和饼图
fig, ax = plt.subplots(figsize=(6, 6))
ax.pie(
    sizes,
    labels=labels,
    autopct='%1.1f%%',     # 百分比显示格式
    startangle=140         # 起始角度，使图更美观
)

# 设置标题
ax.set_title("Resource Allocation by Category")

# 保存图像到文件
output_path = "pie_chart_example.png"
plt.savefig(output_path)

print(f"✅ 饼状图已保存为：{output_path}")
