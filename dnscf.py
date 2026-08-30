def fetch_from_share_link(share_url):
    """从网盘分享链接动态请求 API 获取最新 Token 并下载文本提取 IP"""
    print(f"\n[来源 2] 正在向网盘 API 请求动态 Token: {share_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    share_results = []
    
    # 从主链接中提取唯一 Share Code (如 1c2c1b7dac5944f0bd)
    code_match = re.search(r'/s/([a-f0-9]+)', share_url)
    share_code = code_match.group(1) if code_match else "1c2c1b7dac5944f0bd"
    
    try:
        # 1. 直接请求网盘后台的 API 接口获取真实的临时下载 Token
        api_url = f"http://ilove.pp.ua:5666/api/v1/share/info?code={share_code}"
        token = None
        
        try:
            api_resp = requests.get(api_url, headers=headers, timeout=5)
            if api_resp.status_code == 200:
                data = api_resp.json()
                # 从 API 响应数据中提取 token
                token = data.get("data", {}).get("token") or data.get("token")
        except Exception:
            pass

        # 2. 如果 API 获取失败，则尝试直接正则请求 HTML 源码中的 json 变量
        if not token:
            html_resp = requests.get(share_url, headers=headers, timeout=10)
            token_match = re.search(r'["\']token["\']\s*:\s*["\']([a-f0-9]+)["\']', html_resp.text, re.I)
            if token_match:
                token = token_match.group(1)

        # 3. 组装最终下载 URL
        if token:
            download_url = f"http://ilove.pp.ua:5666/s/download/{share_code}?token={token}"
            print(f"[来源 2] 成功获取动态下载链接: {download_url}")
        else:
            # 最后的备用方案：尝试无 token 路径
            download_url = f"http://ilove.pp.ua:5666/s/download/{share_code}"
            print("[来源 2] 警告: 未能动态获取到 Token，尝试直接请求下载路径...")

        # 4. 下载文件内容并提取 IP
        file_resp = requests.get(download_url, headers=headers, timeout=15)
        if file_resp.status_code == 200:
            file_resp.encoding = 'utf-8'
            content = file_resp.text
            
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                ip = extract_ip_from_line(line)
                if ip:
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 剔除原有数字序号
                    share_results.append(clean_line)
                    
            print(f"[来源 2] 提取成功！共从网盘下载并解析出 {len(share_results)} 条 IP 记录。")
        else:
            print(f"[来源 2] 无法下载文件，HTTP 状态码: {file_resp.status_code}")

    except Exception as e:
        print(f"[来源 2] 执行过程中发生错误: {e}")
        
    return share_results
