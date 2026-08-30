#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 多源提取器 (带动态 Token 解析 & 自动去重)
格式：IP#CA 抓取 172ms 序号
支持：从网页锚点提取 + 从网盘动态提取最新 Token 下载文本并合并
"""

import os
import re
import requests
import time

# --- 来源设置 ---
# 来源 1：原 IP 来源链接（主站首页）
IP_SOURCE_URL = "https://ip.164746.xyz/"

# 来源 2：飞牛/网盘主分享页面链接（不带临时 Token 的主链接）
SHARE_PAGE_URL = "http://ilove.pp.ua:5666/s/1c2c1b7dac5944f0bd"


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
    except:
        pass
    return "UNKNOWN"


def extract_ip_from_line(line):
    """从一行文本中提取出真实的 IP 地址（用于去重判断）"""
    match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
    return match.group(0) if match else None


def fetch_from_share_link(share_url):
    """从主分享页面自动解析最新的下载 Token 并提取 IP"""
    print(f"\n[来源 2] 正在请求分享主页面解析最新下载 Token: {share_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    share_results = []
    
    try:
        resp = requests.get(share_url, headers=headers, timeout=10)
        html = resp.text

        # 1. 尝试从 HTML 或脚本源码中正则匹配带 token 的下载接口/参数
        token_match = re.search(r'token=([a-f0-9]+)', html)
        
        if token_match:
            token = token_match.group(1)
            # 从原始主链接提取唯一的代码标识（例如 1c2c1b7dac5944f0bd）
            code_match = re.search(r'/s/([a-f0-9]+)', share_url)
            code = code_match.group(1) if code_match else "1c2c1b7dac5944f0bd"
            
            # 拼接出包含最新 Token 的真正下载链接
            download_url = f"http://ilove.pp.ua:5666/s/download/{code}?token={token}"
            print(f"成功提取到动态下载链接: {download_url}")
        else:
            # 备用防线：如果网页源码没写死 token，尝试直接拼接带 /download/ 的路径请求
            print("未在源码中直接匹配到 token，尝试使用直连模式请求文件...")
            download_url = share_url.replace("/s/", "/s/download/")

        # 2. 请求下载文件
        file_resp = requests.get(download_url, headers=headers, timeout=15)
        if file_resp.status_code == 200:
            file_resp.encoding = 'utf-8'
            content = file_resp.text
            
            # 从文件文本中逐行提取 IP
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                ip = extract_ip_from_line(line)
                if ip:
                    # 如果原文本里自带格式就提取原格式，否则包装默认格式
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 剔除原有数字序号
                    share_results.append(clean_line)
                    
            print(f"[来源 2] 提取成功，共获取到 {len(share_results)} 个 IP 记录。")
        else:
            print(f"[来源 2] 下载文件失败，HTTP 状态码: {file_resp.status_code}")

    except Exception as e:
        print(f"[来源 2] 提取过程中发生异常: {e}")
        
    return share_results


def fetch_from_web_anchor(web_url):
    """[来源 1] 原有的网页 % 锚点提取逻辑"""
    print(f"\n[来源 1] 开始从主站 ({web_url}) 获取 IP...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    results = []
    
    try:
        response = requests.get(web_url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        html_content = response.text
        
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        ip_matches = list(re.finditer(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', clean_text))
        
        if not ip_matches:
            print("[来源 1] 未能在主页中找到任何有效的 IP 地址。")
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
            print(f"[{index + 1}/{len(target_matches)}] 提取成功 -> {base_formatted}")
            
    except Exception as e:
        print(f"[来源 1] 提取发生错误: {e}")
        
    return results


def main():
    # 1. 执行来源 1 抓取
    web_results = fetch_from_web_anchor(IP_SOURCE_URL)
    
    # 2. 执行来源 2 抓取 (动态获取 Token 并下载)
    share_results = fetch_from_share_link(SHARE_PAGE_URL)
    
    # 本次所有新抓取到的数据汇总
    new_results = web_results + share_results
    
    # 3. 数据去重与编号处理
    seen_ips = set()
    final_lines = []

    # 先加入最新抓取的 IP（新数据优先排在顶部）
    for line in new_results:
        ip = extract_ip_from_line(line)
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            final_lines.append(line)

    # 读取旧文件 ips.txt，剔除新数据中已出现的旧 IP
    if os.path.exists("ips.txt"):
        with open("ips.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 去掉旧序号
                    ip = extract_ip_from_line(clean_line)
                    if ip and ip not in seen_ips:
                        seen_ips.add(ip)
                        final_lines.append(clean_line)

    # 4. 重新从 1 开始生成序号并写回 ips.txt
    with open("ips.txt", "w", encoding="utf-8") as f:
        for idx, item in enumerate(final_lines, start=1):
            f.write(f"{item} {idx}\n")
            
    print(f"\n==========================================")
    print(f"全部完成！汇总后共有 {len(final_lines)} 条 IP 记录。")
    print(f"最新抓取的数据已置顶，重复 IP 已剔除，并重新编号 1 ~ {len(final_lines)} 写入 ips.txt。")


if __name__ == "__main__":
    main()
