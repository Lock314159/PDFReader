## 安装Anaconda

打开这个网站    [清华大学开源软件镜像站](https://mirrors.tuna.tsinghua.edu.cn/)

找到这个目录    Index of /anaconda/archive/

然后一直往下滑

选择这个安装包    Anaconda3-2025.12-2-Windows-x86_64.exe

安装的时候记得勾选环境变量   add annconda 3 to my path environment

或者参考一下手动添加环境变量的视频

[【2025最新】Anaconda下载、安装、环境配置+Pycharm安装、激活、使用教程，零基础必看的保姆级python环境搭建教程！附安装包+激活码！_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1ywpgz3EZv/?spm_id_from=333.337.search-card.all.click&vd_source=c8b2e7d1c7cda75e66fa9c6b32dae868)

## 安装pycharm

直接在官网下载最新版

利用学校给的教育邮箱可以得到一年专业版的许可证

只要还在读书,可以无限续期

细节可以参考这个视频

[Windows | 安装Python和PyCharm_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1Jgf6YvE8e?spm_id_from=333.788.videopod.episodes&vd_source=c8b2e7d1c7cda75e66fa9c6b32dae868&p=3)

## 配置python环境

按住 win+r,输入 cmd 打开命令窗口输入这串代码

```
conda create -n PDFreader python=3.9
```

其中 PDFreader 是新环境的名字,python=3.9 指定了 Python 的版本

按下回车即可开始创建环境,在创建环境中可以会有提示说需要下载某些模块

输入“y”,同意并继续创建

创建好的环境文件路径如"安装目录\Anaconda\envs\环境名称""

## 激活环境

按住 win+r,输入 cmd 打开命令窗口输入这串代码

```
conda activate 环境名字
```

回车,随后会出现

```
(环境名字)c:\users\用户名>
```

## 添加国内镜像网站加快下载速度

按住 win+r,输入 cmd 打开命令窗口输入这串代码

```
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
```

```
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
```

```
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
```

```
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/pro
```

```
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
```



## 安装依赖

在命令行输入以下代码    *<mark>一定要先激活环境</mark>*

```
pip install PyQt5 PyMuPDF pyinstaller Pillow
```

安装了一些库

## 运行python程序(.py)并打包成(.exe)方便后续使用

下面是我通过ds生成的代码,可以随时向ds提出需求,定制自己的小工具

这个是初始版    [DeepSeek](https://chat.deepseek.com/share/6xf4chjazfoik7kbwn)

经过穷追不舍的定制

这个是最终版    [DeepSeek](https://chat.deepseek.com/share/i6qnr4nkf7c8az7f1l)

记得下载那个完整代码,一定要记得文件目录

<mark>CTRL+shift+c</mark>    快速复制文件目录    例如    "F:\user\下载\测试6.py"

---

按住 win+r,输入 cmd 打开命令窗口输入这串代码    *<mark>一定要激活环境</mark>*

```
python 文件目录
```

会弹出软件窗口,这里我们可以试用功能或者看看ui

---

```
pyinstaller --onefile --windowed --name 软件名称 python文件目录
```

然后稍作等待,软件就会打包成一个可执行文件(.exe)

文件默认保存目录    "C:\Users\用户名\dist"   

然后就可以使用了
