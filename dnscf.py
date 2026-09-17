#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 提取与分类器

规则：
1. https://ip.164746.xyz 和 WEBDAV_URL (443端口) 提取到的 IP：
   - 172.64 网段 -> jp.txt (命名格式: IP#JP 443 序号)
   - 104.18 网段 -> sp.txt (命名格式: IP#SP 443 序号)
2. WEBDAV_URL2 (8443端口) 提取到的 IP：
   - 172.64 网段 -> jp8443.txt (命名格式: IP#JP 8443 序号)
   - 104.18 网段 -> sp8443.txt (命名格式: IP#SP 8443 序号)
3. 其余网段 IP 合并保存至 ips.txt (命名格式: IP#CA 自用 443 序号)
"""

import os
import re
import requests
from requests.auth import HTTPBasicAuth

IP_SOURCE_URL = "https://ip.164746.xyz/"


def extract_ip_from_line(line):
    """从一行文本中提取出真实的 IP 地址"""
    match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', line)
    return match.group(0) if match else None


def fetch_from_web_anchor(web_url):
    """[来源 1] 从网页提取 IP 列表"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    results = []
    
    try:
        response = requests.get(web_url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        html_content = response.text
        
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        ip_matches = list(re.finditer(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', clean_text))
        
        if not ip_matches:
            return results
            
        target_matches = ip_matches[:10]
        
        for match in target_matches:
            results.append(match.group(0))
            
    except Exception:
        pass
        
    return results


def fetch_from_webdav_url(webdav_url):
    """通用的 WebDAV 文件读取逻辑，返回纯 IP 列表"""
    nas_user = os.environ.get("NAS_USER")
    nas_pass = os.environ.get("NAS_PASS")

    share_results = []

    if not webdav_url or not nas_user or not nas_pass:
        return share_results

    try:
        import requests.packages.urllib3
        requests.packages.urllib3.disable_warnings()

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(
            webdav_url,
            auth=HTTPBasicAuth(nas_user, nas_pass),
            headers=headers,
            timeout=15,
            verify=False
        )

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
                    share_results.append(ip)

    except Exception:
        pass
        
    return share_results


def process_and_save_ips(new_ips, prefix_format, target_file, max_limit=15):
    """去重、合并历史记录、限制最多保留 max_limit 条，追加序号并写入文件"""
    seen_ips = set()
    final_ips = []

    for ip in new_ips:
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            final_ips.append(ip)

    if os.path.exists(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ip = extract_ip_from_line(line)
                    if ip and ip not in seen_ips:
                        seen_ips.add(ip)
                        final_ips.append(ip)

    final_ips = final_ips[:max_limit]

    with open(target_file, "w", encoding="utf-8") as f:
        for idx, ip in enumerate(final_ips, start=1):
            line_str = f"{ip}#{prefix_format} {idx}"
            f.write(f"{line_str}\n")


def categorize_ips(ip_list):
    """根据 IP 网段划分"""
    jp_ips = []
    sp_ips = []
    other_ips = []

    for ip in ip_list:
        if ip.startswith("172.64."):
            jp_ips.append(ip)
        elif ip.startswith("104.18."):
            sp_ips.append(ip)
        else:
            other_ips.append(ip)

    return jp_ips, sp_ips, other_ips


def main():
    webdav_url_443 = os.environ.get("WEBDAV_URL")
    webdav_url_8443 = os.environ.get("WEBDAV_URL2")

    web_results = fetch_from_web_anchor(IP_SOURCE_URL)
    dav_results_443 = fetch_from_webdav_url(webdav_url_443)
    dav_results_8443 = fetch_from_webdav_url(webdav_url_8443)

    all_443_ips = web_results + dav_results_443
    jp_443, sp_443, other_443 = categorize_ips(all_443_ips)
    jp_8443, sp_8443, other_8443 = categorize_ips(dav_results_8443)

    all_other_ips = other_443 + other_8443

    process_and_save_ips(jp_443, "JP 443", "jp.txt", max_limit=15)
    process_and_save_ips(sp_443, "SP 443", "sp.txt", max_limit=15)
    
    process_and_save_ips(jp_8443, "JP 8443", "jp8443.txt", max_limit=15)
    process_and_save_ips(sp_8443, "SP 8443", "sp8443.txt", max_limit=15)

    process_and_save_ips(all_other_ips, "CA 自用 443", "ips.txt", max_limit=15)


if __name__ == "__main__":
    main()
