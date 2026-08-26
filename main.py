name: Cloudflare IP Auto Fetch

on:
  # 定时触发：每 6 小时自动运行一次 (UTC 时间 0:00, 6:00, 12:00, 18:00)
  schedule:
    - cron: '0 */6 * * *'
  # 支持在 GitHub 页面手动点击按钮立即触发运行
  workflow_dispatch:

jobs:
  build-and-run:
    runs-on: ubuntu-latest

    steps:
    # 1. 拉取仓库代码
    - name: Checkout repository
      uses: actions/checkout@v4

    # 2. 配置 Python 环境
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    # 3. 安装依赖库
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests

    # 4. 执行你的 Python 脚本（假设脚本文件名是 main.py）
    - name: Run IP Extractor Script
      run: python main.py

    # 5. 将生成的 ips.txt 提交并推送到仓库
    - name: Commit and push updated ips.txt
      run: |
        git config --local user.email "github-actions[bot]@users.noreply.github.com"
        git config --local user.name "github-actions[bot]"
        git add ips.txt
        # 仅在文件有更新时提交，避免无变动报错
        git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-update ips.txt [skip ci]" && git push)
