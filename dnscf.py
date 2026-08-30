#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 提取器 (丢包率坐标精准版)
利用 % (丢包率) 作为锚点，精准抓取其右侧紧邻的真实平均延迟，彻底解决 4ms 误差
格式：IP#CA 抓取 172ms 序号 (新抓取的排在最前，自动剔除旧的重复 IP，全量重新排序)
"""

import os
import re
import requests
import time

# 优选 IP 的来源链接（主站首页）
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
    except:
        pass
    return "UNKNOWN"

def extract_ip_from_line(line):
    """从一行文本中提取出真实的 IP 地址（用于去重判断）"""
    match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
    return match.group(0) if match else None

def main():
    print(f"开始从主站 ({IP_SOURCE_URL}) 获取 Cloudflare 优选 IP...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        response = requests.get(IP_SOURCE_URL, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        html_content = response.text
        
        # 剥离所有 HTML 标签，留出干净的纯文本内容
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        
        # 找出文本中所有的 IPv4 地址及其在文中的具体物理位置
        ip_matches = list(re.finditer(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', clean_text))
        
        if not ip_matches:
            print("错误：未能在主页中找到任何有效的 IP 地址。")
            return
            
        print(f"成功定位到主页中总共存在 {len(ip_matches)} 个 IP 锚点...")
        
        new_results = []
        # 限制最多处理前 10 个优选 IP
        target_matches = ip_matches[:10]
        
        print("开始通过【% 锚点法】精准绕过发送/接收包，抓取真实延迟...")
        for index, match in enumerate(target_matches):
            ip = match.group(0)
            
            # 计算当前 IP 的专属数据区块范围
            start_pos = match.end()
            end_pos = ip_matches[index + 1].start() if (index + 1) < len(ip_matches) else len(clean_text)
            context = clean_text[start_pos:end_pos]
            
            tokens = context.split()
            latency = "测速ms"
            
            # --- 核心修复：追踪 % 坐标 ---
            for i, token in enumerate(tokens):
                if '%' in token:  # 找到了丢包率（如 0.00%）
                    if i + 1 < len(tokens):  # 确保后面还有数据
                        next_token = tokens[i + 1]  # 丢包率后面的那一个词，铁定是平均延迟！
                        
                        # 提取其中的数字（丢掉可能残存的单位或杂质）
                        num_match = re.search(r'\d+(?:\.\d+)?', next_token)
                        if num_match:
                            num_val = float(num_match.group(0))
                            # 转成纯整数，去掉小数点尾巴，看起来更清爽（如 172.45 -> 172ms）
                            latency = f"{int(num_val)}ms"
                        break  # 抓到了就立马退出当前 IP 的查找
            
            # 安全限速：请求三方 GeoIP 数据库，每查一个 IP 强制歇 2 秒防止被封
            if index > 0:
                time.sleep(2)
                
            # 获取该 IP 的地理国家
            country_code = get_ip_location(ip)
            
            # 基础格式（暂不加序号，等后续统一编号）
            base_formatted = f"{ip}#CA 抓取 {latency}"
            new_results.append(base_formatted)
            
            print(f"[{index + 1}/{len(target_matches)}] 提取成功 -> {base_formatted}")

        # --- 核心修改：读取旧数据 + 剔除重复 IP ---
        seen_ips = set()       # 记录已经出现的 IP
        final_lines = []       # 最终要保存的所有行（基础文本，无序号）

        # 1. 优先放入最新抓取的 IP
        for line in new_results:
            ip = extract_ip_from_line(line)
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                final_lines.append(line)

        # 2. 读取旧文件，如果 IP 已经存在于 seen_ips，则跳过（即剔除旧的重复 IP）
        if os.path.exists("ips.txt"):
            with open("ips.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # 正则剥离末尾的数字序号，还原基础内容
                        clean_line = re.sub(r'\s+\d+$', '', line)
                        ip = extract_ip_from_line(clean_line)
                        
                        # 如果这个旧 IP 在新抓取的列表里没出现过，才保留它
                        if ip and ip not in seen_ips:
                            seen_ips.add(ip)
                            final_lines.append(clean_line)

        # 3. 重新从 1 开始编写序号并写入 ips.txt
        with open("ips.txt", "w", encoding="utf-8") as f:
            for idx, item in enumerate(final_lines, start=1):
                f.write(f"{item} {idx}\n")
                
        print(f"\n大功告成！已成功将本次新抓取的 IP 插入顶部，剔除了旧文件中的重复 IP，并对全量数据（共 {len(final_lines)} 条）重新完成了 1 ~ {len(final_lines)} 的序号编排！")

    except Exception as e:
        print(f"执行过程中发生错误: {e}")

if __name__ == "__main__":
    main()
