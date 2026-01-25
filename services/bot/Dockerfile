# 使用全量 Bookworm 镜像以包含所有编译工具，避免 slim 模式极易出现的构建失败
FROM python:3.11-bookworm

WORKDIR /app

# 设置 APT / PIP 镜像源 (清华大学 Tuna) 以应对网络不稳定
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装中文字体和 Git
RUN apt-get update && apt-get install -y fonts-noto-cjk git && rm -rf /var/lib/apt/lists/*

# 配置 Git 基础身份（用于容器内自动提交）
RUN git config --global user.name "LCARS Main Computer" && \
    git config --global user.email "computer@starfleet.federation" && \
    git config --global --add safe.directory "*"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝代码和静态资源
COPY app ./app

ENV PORT=8080
EXPOSE 8080

# 增加 --log-level debug 方便用户排查
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8080","--log-level","debug"]
