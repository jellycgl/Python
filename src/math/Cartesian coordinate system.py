import math
import numpy as np #导入数值计算模块
import matplotlib.pyplot as plt #导入绘图模块
import mpl_toolkits.axisartist as axisartist #导入坐标轴加工模块


def draw_sin():
    fig = plt.figure(figsize=(20,20)) #新建画布
    ax = axisartist.Subplot(fig,111) #使用axisartist.Subplot方法创建一个绘图区对象ax
    fig.add_axes(ax) #将绘图区对象添加到画布中

    ax.axis[:].set_visible(False) #隐藏原来的实线矩形

    ax.axis["x"]=ax.new_floating_axis(0, 0, axis_direction="bottom") #添加x轴
    ax.axis["y"]=ax.new_floating_axis(1, 0, axis_direction="bottom") #添加y轴

    ax.axis["x"].set_axisline_style("->", size=1.0) #给x坐标轴加箭头
    ax.axis["y"].set_axisline_style("->", size=1.0) #给y坐标轴加箭头
    ax.annotate(s='x' , xy=(1.0,0), xytext=(10,0.1)) #标注x轴
    ax.annotate(s='y' , xy=(0,1.0), xytext=(-0.2,3.0)) #标注y轴

    plt.xlim(-10,10) #设置横坐标范围
    plt.ylim(-3,3) #设置纵坐标范围
    #ax.set_xticks([-2*math.pi,-math.pi,0,math.pi,2*math.pi]) #设置x轴刻度
    ax.set_xticks([-10, -9, -8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,9,10]) #设置x轴刻度
    ax.set_yticks([-3,-2,-1, 1,2,3]) #设置y轴刻度

    y = []
    x = np.linspace(-2*math.pi, 2*math.pi,100) #构造横坐标数据
    for xi in x:
        y.append(math.sin(xi))
    plt.plot(x,y,color="blue") #描点连线
    plt.show() #出图
    return x, y

def draw_grid():
    plt.gcf().set_facecolor(np.ones(3) * 240 / 255)
    plt.xticks(np.arange(1, 51, 1))
    plt.yticks(np.arange(1, 51, 1))
    plt.grid(c='g', linestyle='-.')
    plt.show()

if __name__ == "__main__":
    draw_grid()