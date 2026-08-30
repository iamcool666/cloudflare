#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 提取器 (双来源去重及安全诊断版)
来源 1: 网页锚点提取 (https://ip.164746.xyz/)
来源 2: 飞牛 NAS WebDAV 安全读取 (环境变量 + 自动诊断)
格式：IP#CA 抓取 172ms 序号
"""

import os
import re
import time
import requests
from requests.auth import HTTPBasicAuth

# 来源 1：主站 URL
IP_SOURCE_URL = "https://ip.164746.xyz/"


def get_ip_location(ip):
    """通过 ip-api 数据库获取 IP 对应的国家代码"""
    try:
        api_url = f"http://ip-api.com/json/{ip}?fields=status,countryCode"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(api_url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data.get('countryCode', '').upper()
    except Exception:
        pass
    return "UNKNOWN"


def extract_ip_from_line(line):
    """从一行文本中提取出真实的 IP 地址（用于去重判断）"""
    match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
    return match.group(0) if match else None


def fetch_from_web_anchor(web_url):
    """[来源 1] 从网页通过 % 锚点法提取 IP"""
    print(f"\n[来源 1] 开始从主站 ({web_url}) 获取 Cloudflare 优选 IP...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    results = []
    
    try:
        response = requests.get(web_url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        html_content = response.text
        
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        ip_matches = list(re.finditer(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', clean_text))
        
        if not ip_matches:
            print("[来源 1] 错误：未能在主页中找到任何有效的 IP 地址。")
            return results
            
        print(f"[来源 1] 成功定位到 {len(ip_matches)} 个 IP 锚点，提取前 10 个...")
        target_matches = ip_matches[:10]
        
        for index, match in enumerate(target_matches):
            ip = match.group(0)
            start_pos = match.end()
            end_pos = ip_matches[index + 1].start() if (index + 1) < len(ip_matches) else len(clean_text)
            context = clean_text[start_pos:end_pos]
            
            tokens = context.split()
            latency = "测速ms"
            
            for i, token in enumerate(tokens):
                if '%' in token:
                    if i + 1 < len(tokens):
                        next_token = tokens[i + 1]
                        num_match = re.search(r'\d+(?:\.\d+)?', next_token)
                        if num_match:
                            latency = f"{int(float(num_match.group(0)))}ms"
                        break
            
            if index > 0:
                time.sleep(2)
                
            country_code = get_ip_location(ip)
            base_formatted = f"{ip}#CA 抓取 {latency}"
            results.append(base_formatted)
            print(f"[来源 1] [{index + 1}/{len(target_matches)}] 提取成功 -> {base_formatted}")
            
    except Exception as e:
        print(f"[来源 1] 提取过程发生错误: {e}")
        
    return results


def fetch_from_webdav():
    """[来源 2] 通过 WebDAV + 环境变量安全读取飞牛 NAS 上的 ip_best.txt"""
    # 优先从环境变量获取，如不存在则使用默认路径
    webdav_url = os.environ.get("WEBDAV_URL", "https://ilove.pp.ua:5006/docker/cf-speedtest/ip_best.txt")
    nas_user = os.environ.get("NAS_USER")
    nas_pass = os.environ.get("NAS_PASS")

    print(f"\n[来源 2] 正在向 WebDAV 请求文件: {webdav_url}")
    share_results = []

    # 1. 环境变量缺失检查
    if not nas_user or not nas_pass:
        print("[来源 2] 警告: 未检测到 NAS_USER 或 NAS_PASS 环境变量，跳过 WebDAV 读取。")
        print("          请检查 GitHub Secrets 中是否添加了 NAS_USER 与 NAS_PASS。")
        return share_results

    try:
        # 忽略 SSL 警告（防止自签名或 DDNS 证书报错）
        import requests.packages.urllib3
        requests.packages.urllib3.disable_warnings()

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(
            webdav_url,
            auth=HTTPBasicAuth(nas_user, nas_pass),
            headers=headers,
            timeout=15,
            verify=False  # 禁用 SSL 验证，确保连接成功
        )

        print(f"[来源 2] 服务器响应状态码: HTTP {response.status_code}")

        if response.status_code == 200:
            response.encoding = 'utf-8'
            content = response.text
            
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                ip = extract_ip_from_line(line)
                if ip:
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 剔除原有的数字序号
                    share_results.append(clean_line)
                    
            print(f"[来源 2] 读取成功！解析出 {len(share_results)} 条 IP 记录。")
        elif response.status_code == 401:
            print("[来源 2] 报错 401 (未授权): 请检查 Secret 中的 NAS_USER 和 NAS_PASS 是否正确，或账号是否有该目录只读权限。")
        elif response.status_code == 404:
            print("[来源 2] 报错 404 (未找到): 路径不正确。请在 WEBDAV_URL 中尝试去掉 /docker 试下是否为根目录映射。")
        else:
            print(f"[来源 2] 请求未成功，返回内容预览: {response.text[:150]}")

    except Exception as e:
        print(f"[来源 2] 连接 WebDAV 过程发生异常: {e}")
        
    return share_results


def main():
    # 1. 抓取来源 1（网页）
    web_results = fetch_from_web_anchor(IP_SOURCE_URL)
    
    # 2. 读取来源 2（WebDAV）
    dav_results = fetch_from_webdav()
    
    # 汇总两个来源的新数据（来源 1 优先于 来源 2）
    new_results = web_results + dav_results
    
    # 3. 数据跨源去重与自动编号
    seen_ips = set()
    final_lines = []

    # 先装载本次新抓取的 IP（新数据排在最顶部）
    for line in new_results:
        ip = extract_ip_from_line(line)
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            final_lines.append(line)

    # 再读取本地仓库旧的 ips.txt，补充历史未重复的 IP
    if os.path.exists("ips.txt"):
        with open("ips.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 剔除原有数字序号
                    ip = extract_ip_from_line(clean_line)
                    if ip and ip not in seen_ips:
                        seen_ips.add(ip)
                        final_lines.append(clean_line)

    # 4. 重新从 1 开始自动追加序号并写入 ips.txt
    with open("ips.txt", "w", encoding="utf-8") as f:
        for idx, item in enumerate(final_lines, start=1):
            f.write(f"{item} {idx}\n")
            
    print(f"\n==========================================")
    print(f"处理完成！")
    print(f"来源 1 获取 {len(web_results)} 条 | 来源 2 获取 {len(dav_results)} 条")
    print(f"跨源去重及合并后，共有 {len(final_lines)} 条 IP 记录已写入 ips.txt 并完成 1~{len(final_lines)} 重新编号。")


if __name__ == "__main__":
    main()
