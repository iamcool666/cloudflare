#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 提取器 (网段归类版)
来源 1: 网页锚点提取 (https://ip.164746.xyz/) -> 443
来源 2: 飞牛 NAS WebDAV 读取 WEBDAV_URL (ip_best_443.txt) -> 443
来源 3: 飞牛 NAS WebDAV 读取 WEBDAV_URL2 (ip_best_8443.txt) -> 8443

输出逻辑:
- 443 来源 172.64 网段 -> jp.txt (ip#JP 443 序号)
- 443 来源 104.18 网段 -> sg.txt (ip#SG 443 序号)
- 8443 来源 172.64 网段 -> jp8443.txt (ip#JP 8443 序号)
- 8443 来源 104.18 网段 -> sg8443.txt (ip#SG 8443 序号)
- 所有其余网段合并保存 -> ips.txt (ip#CA 自用 443 序号)
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


def clean_latency_suffix(line):
    """统一清除行内的延迟信息（例如清除 -78ms、 78ms 或 测速ms）"""
    line = re.sub(r'-\d+ms', '', line)
    line = re.sub(r'\s+\d+ms', '', line)
    line = re.sub(r'\s+测速ms', '', line)
    return line


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
                
            base_formatted = f"{ip}#CA 自用 443 {latency}"
            results.append(base_formatted)
            print(f"[来源 1] [{index + 1}/{len(target_matches)}] 提取成功 -> {base_formatted}")
            
    except Exception as e:
        print(f"[来源 1] 提取过程发生错误: {e}")
        
    return results


def fetch_from_webdav_url(webdav_url, tag="来源 2"):
    """通用的 WebDAV 文件读取逻辑"""
    nas_user = os.environ.get("NAS_USER")
    nas_pass = os.environ.get("NAS_PASS")

    print(f"\n[{tag}] 正在向 WebDAV 请求文件: {webdav_url}")
    share_results = []

    if not webdav_url:
        print(f"[{tag}] 警告: 未检测到对应 WebDAV URL 环境变量，跳过读取。")
        return share_results

    if not nas_user or not nas_pass:
        print(f"[{tag}] 警告: 未检测到 NAS_USER 或 NAS_PASS 环境变量，跳过 WebDAV 读取。")
        print("      请检查 GitHub Secrets 中是否添加了 NAS_USER 与 NAS_PASS。")
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

        print(f"[{tag}] 服务器响应状态码: HTTP {response.status_code}")

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
                    
            print(f"[{tag}] 读取成功！解析出 {len(share_results)} 条 IP 记录。")
        elif response.status_code == 401:
            print(f"[{tag}] 报错 401 (未授权): 请检查 Secret 中的 NAS_USER 和 NAS_PASS 是否正确。")
        elif response.status_code == 404:
            print(f"[{tag}] 报错 404 (未找到): 路径不正确，请检查 WebDAV 文件路径。")
        else:
            print(f"[{tag}] 请求未成功，返回内容预览: {response.text[:150]}")

    except Exception as e:
        print(f"[{tag}] 连接 WebDAV 过程发生异常: {e}")
        
    return share_results


def reformat_line_remark(line, new_label):
    """重新替换或构造行中的备注标签（保持 IP 和后缀延迟不变）"""
    ip = extract_ip_from_line(line)
    if not ip:
        return line
    
    # 匹配并获取 IP 后的延迟部分（如 测速ms 或 78ms）
    latency_match = re.search(r'(\d+ms|测速ms)', line)
    latency_str = f" {latency_match.group(1)}" if latency_match else ""
    
    # 构建统一的标准新行，例如 "172.64.1.1#JP 443 78ms"
    return f"{ip}#{new_label}{latency_str}"


def process_and_save_ips(new_data, target_file, max_limit=15):
    """去重、剔除旧序号、合并历史记录、限制最多保留 max_limit 条，重新从 1 开始编号并保存"""
    seen_ips = set()
    final_lines = []

    # 1. 优先装载本次最新抓取的 IP
    for line in new_data:
        ip = extract_ip_from_line(line)
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            cleaned_line = clean_latency_suffix(line)
            final_lines.append(cleaned_line)

    # 2. 读取历史文件，补充尚未重复的历史 IP
    if os.path.exists(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    clean_line = re.sub(r'\s+\d+$', '', line)  # 剔除旧数字序号
                    clean_line = clean_latency_suffix(clean_line)  # 清理延迟后缀
                    ip = extract_ip_from_line(clean_line)
                    if ip and ip not in seen_ips:
                        seen_ips.add(ip)
                        final_lines.append(clean_line)

    # 3. 截取最多 max_limit (15) 条，优先剔除最早的 IP
    final_lines = final_lines[:max_limit]

    # 4. 重新从 1 开始追加序号并写入文件
    with open(target_file, "w", encoding="utf-8") as f:
        for idx, item in enumerate(final_lines, start=1):
            f.write(f"{item} {idx}\n")

    return len(final_lines)


def main():
    webdav_url_443 = os.environ.get("WEBDAV_URL")
    webdav_url_8443 = os.environ.get("WEBDAV_URL2")

    web_results = fetch_from_web_anchor(IP_SOURCE_URL)
    dav_results_443 = fetch_from_webdav_url(webdav_url_443, tag="来源 2 (443)")
    dav_results_8443 = fetch_from_webdav_url(webdav_url_8443, tag="来源 3 (8443)")

    # 结果分类容器
    jp_443_list = []
    sg_443_list = []
    jp_8443_list = []
    sg_8443_list = []
    other_list = []

    # 处理 443 来源数据 (来源 1 和 来源 2)
    for line in web_results + dav_results_443:
        ip = extract_ip_from_line(line)
        if not ip:
            continue
        if ip.startswith("172.64."):
            jp_443_list.append(reformat_line_remark(line, "JP 443"))
        elif ip.startswith("104.18."):
            sg_443_list.append(reformat_line_remark(line, "SG 443"))
        else:
            other_list.append(reformat_line_remark(line, "CA 自用 443"))

    # 处理 8443 来源数据 (来源 3)
    for line in dav_results_8443:
        ip = extract_ip_from_line(line)
        if not ip:
            continue
        if ip.startswith("172.64."):
            jp_8443_list.append(reformat_line_remark(line, "JP 8443"))
        elif ip.startswith("104.18."):
            sg_8443_list.append(reformat_line_remark(line, "SG 8443"))
        else:
            other_list.append(reformat_line_remark(line, "CA 自用 443"))

    # 写入各分类文件
    count_jp = process_and_save_ips(jp_443_list, "jp.txt", max_limit=15)
    count_sg = process_and_save_ips(sg_443_list, "sg.txt", max_limit=15)
    count_jp8443 = process_and_save_ips(jp_8443_list, "jp8443.txt", max_limit=15)
    count_sg8443 = process_and_save_ips(sg_8443_list, "sg8443.txt", max_limit=15)
    count_other = process_and_save_ips(other_list, "ips.txt", max_limit=15)

    print(f"\n==========================================")
    print(f"处理完成！")
    print(f"[jp.txt]      (172.64 网段 443)  : 已保存 {count_jp} 条 (1~{count_jp})")
    print(f"[sg.txt]      (104.18 网段 443)  : 已保存 {count_sg} 条 (1~{count_sg})")
    print(f"[jp8443.txt]  (172.64 网段 8443) : 已保存 {count_jp8443} 条 (1~{count_jp8443})")
    print(f"[sg8443.txt]  (104.18 网段 8443) : 已保存 {count_sg8443} 条 (1~{count_sg8443})")
    print(f"[ips.txt]     (其余合并网段)     : 已保存 {count_other} 条 (1~{count_other})")


if __name__ == "__main__":
    main()
