import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates

# 示例数据
# 示例数据：每个版本对应一个发布时间的列表
version_data = {
    "R11.0": ["2022-03-11", 
              "2022-04-07", "2022-04-11", "2022-04-13", "2022-04-19", "2022-04-20", "2022-04-21", "2022-04-22", "2022-04-25", "2022-04-27", "2022-04-28", "2022-04-30",
              "2022-05-04", "2022-05-05", "2022-05-06", "2022-05-13", "2022-05-20", "2022-05-22", "2022-05-26", "2022-05-29", "2022-05-30", "2022-05-31",
              "2022-06-01", "2022-06-03", "2022-06-07", "2022-06-08", "2022-06-10", "2022-06-14", "2022-06-18", "2022-06-21", "2022-06-24",
              "2022-07-02", "2022-07-10", "2022-07-14", "2022-07-18","2022-07-22","2022-07-27","2022-07-14",
              "2022-08-01","2022-08-03","2022-08-10","2022-08-17","2022-08-23","2022-08-26",
              "2022-09-09","2022-09-16","2022-09-23","2022-10-14",
              "2022-10-19","2022-10-21","2022-10-27","2022-11-01",
              "2022-11-03","2022-11-08","2022-11-11","2022-11-15","2022-11-17","2022-11-22","2022-11-25","2022-11-28"
              ],
    "R11.0a": ["2022-12-01", "2022-12-07", "2022-12-09", "2022-12-16", "2022-12-23", 
               "2023-01-07", "2023-01-15", "2023-01-20", "2023-01-27", 
               "2023-02-03","2023-02-07","2023-02-13","2023-02-17","2023-02-24",
               "2023-03-03","2023-03-17","2023-03-24","2023-03-31"
              ],
    "R11.1":  ["2023-04-21",
               "2023-05-05","2023-05-12","2023-05-19",
               "2023-06-02","2023-06-09","2023-06-16","2023-06-23","2023-06-30",
               "2023-07-07","2023-07-14","2023-07-21",
               "2023-08-05","2023-08-12","2023-08-18","2023-08-25"
              ],
    "R11.1a": ["2023-09-01", "2023-09-10", "2023-09-15", "2023-09-22","2023-09-30",
               "2023-10-06", "2023-10-14", "2023-10-20", "2023-10-30",
               "2023-11-03", "2023-11-10", "2023-11-17", "2023-11-24",
               "2023-12-02", "2023-12-09", "2023-12-16", "2023-12-24", "2023-12-27",  
               "2024-01-06", "2024-01-13", "2024-01-19", "2024-01-20"
              ],
    "R11.1b": ["2024-02-01", "2024-02-16", 
               "2024-03-08", "2024-03-16", "2024-03-23", "2024-03-28", 
               "2024-04-05", "2024-04-13", "2024-04-20", "2024-04-26", 
               "2024-05-12", "2024-05-17", "2024-05-26", 
               "2024-06-01", "2024-06-23", 
               "2024-07-06", "2024-07-15", "2024-07-19", 
               "2024-08-03", "2024-08-12", "2024-08-30", 
               "2024-09-07", 
               "2024-10-12", 
               "2024-11-14",
               "2025-01-10"
              ],
    "10.1.9(Jap)": [
                "2023-09-01",
                "2024-07-06", "2024-07-18",
                "2024-10-08", "2024-10-15", "2024-10-17", "2024-10-30",
                "2024-11-12",
                "2024-12-06", "2024-12-13", "2024-12-17", "2024-12-31",
                "2025-01-10"
              ],
    "R12.0":  ["2025-02-15",
               "2025-05-09"
              ],
    "R12.1":  ["2025-04-29",
               "2025-05-09", "2025-05-23"
            ]  
}

# 将字符串转换为 datetime 对象
for version in version_data:
    version_data[version] = [datetime.strptime(date, "%Y-%m-%d") for date in version_data[version]]

# 创建图形和坐标轴
fig, ax = plt.subplots(figsize=(10, 6))

# 为每个版本画出时间点（横坐标为时间，纵坐标为版本索引）
for idx, (version, dates) in enumerate(version_data.items()):
    y_positions = [idx] * len(dates)
    ax.plot(dates, y_positions, 'o-', label=version)

# 设置 Y 轴：版本标签
ax.set_yticks(range(len(version_data)))
ax.set_yticklabels(version_data.keys())

# 设置 X 轴：日期格式
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

# 添加图表元素
plt.xlabel("Date")
plt.ylabel("Version")
plt.title("Version Release Timeline")
plt.grid(True)
plt.tight_layout()
plt.legend()

# 保存和展示图像
plt.savefig("version_release_timeline.png")
plt.show()
