#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用qwen3-VL-235B模型将图文交错数据转换为多轮图文对(Q&A)格式
修改：在输出中增加 'origin' 字段保留原始数据
"""

import copy
import json
import requests
import base64
import os
import sys
import threading
import time
import re
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def check_image(img_path):
    """检查图片有效性"""
    try:
        with Image.open(img_path) as image:
            image.verify()
        return True
    except:
        return False

def image_to_base64(img_path):
    """图片转Base64"""
    with open(img_path, 'rb') as f:
        return str(base64.b64encode(f.read()), 'utf-8')

def construct_image_urls(data_line):
    """
    根据JSON数据构造图片URL列表
    使用 data_line['prefix'] 作为路径前缀
    """
    prefix = data_line.get('prefix', '')
    img_list = data_line.get('img', [])
    
    image_urls = []
    for img_name in img_list:
        # 拼接完整路径
        img_path = os.path.join("/home/tione/notebook/parsing/code/repo", img_name)
        
        if os.path.exists(img_path):
            # 简单检查文件大小不为0
            if os.path.getsize(img_path) > 0:
                try:
                    base64_str = image_to_base64(img_path)
                    image_urls.append(f"data:image/jpeg;base64,{base64_str}")
                except Exception as e:
                    print(f"图片转码失败: {img_path}, {e}")
            else:
                print(f"警告: 图片为空文件: {img_path}")
        else:
            print(f"警告: 图片文件不存在: {img_path}")
    
    return image_urls

# ================= 模型交互核心逻辑 =================

def call_qwen3_vl_model(image_urls, raw_text, service_url):
    """
    调用模型进行推理
    Prompt经过专门设计，用于提取Q&A并保留占位符
    """
    
    system_prompt = """你是一个专业的教育内容专家和数据处理助手。
你的任务是改写给定的图文交错文本，改为一组高质量的“问题-答案”对（Q&A）。

请严格遵守以下规则：
1. **输出格式**：必须直接返回一个合法的 JSON 列表，格式为 `[{"question": "...", "answer": "..."}, ...]`。不要包含 Markdown 代码块标记（如 ```json），不要包含任何其他开场白或结束语。
2. **语言一致性**：保持生成的“问题-答案”对
3. **内容覆盖**：
   - 问题（question）应该和图片关联紧密，同时由两个部分构成：1）题干：对原始文本的相关背景进行改写，去除该部分内容的上下文依赖，作为题干、2）题目：题目应该尽可能详尽，帮助用户对图片进行理解。
   - 答案（answer）必须完全忠实于原文(如果原始数据中确实不包含答案，则答案处填写“无合理答案”)，同时需要尽可能包含详尽的推理过程。
4. **关键要求 - 图片占位符**：
   - 图片占位符格式为`<ut_im##age_here_index>数字</ut_im##age_here_index>`。
   - 你必须在生成的“question”中保留这些占位符，将占位符放置在题目中描述该图片内容或引用该图片的最合适位置。
   - **绝对不要在“answer”中包含这些占位符**。
   - **绝对不要修改占位符的格式，或者删除占位符**。
"""

    user_text_prompt = f"""请处理以下图文内容。
图文内容：
{raw_text}

请生成 JSON 格式的 Q&A 列表："""

    # 构造消息体
    messages_content = [
        {"role": "system", "content": system_prompt}
    ]
    
    user_content = []
    # 1. 先放入图片
    for img_url in image_urls:
        user_content.append({
            "type": "image_url", 
            "image_url": {"url": img_url},
            "min_pixels": 224 * 224,
            "max_pixels": 1280 * 28 * 28,
        })
    
    # 2. 再放入文本
    user_content.append({
        "type": "text", 
        "text": user_text_prompt
    })
    
    messages_content.append({
        "role": "user", 
        "content": user_content
    })
    
    payload = {
        "messages": messages_content,
        'temperature': 0, # 降低温度以保证格式稳定
        'repetition_penalty': 1.05,
        'max_tokens': 4096, # 增加token数以容纳长文本
    }
    
    headers = {"Content-Type": "application/json"}
    
    # 重试逻辑
    for retry in range(MAX_RETRIES + 1):
        try:
            response = requests.post(service_url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                return content
            else:
                raise ValueError("模型返回结果为空或格式错误")
                
        except Exception as e:
            reset_thread_service_url() # 发生错误重置URL
            if retry < MAX_RETRIES:
                # print(f"调用失败 ({e})，线程 {threading.current_thread().name} 正在重试 {retry+1}...")
                service_url = get_thread_service_url() # 重新获取URL
                time.sleep(RETRY_DELAY)
            else:
                print(f"线程 {threading.current_thread().name} 模型调用最终失败: {e}")
                return None
    return None

def parse_model_response(response_text):
    """
    解析模型返回的JSON字符串
    """
    if not response_text:
        return None
    
    # 清洗可能存在的 Markdown 标记
    cleaned_text = response_text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    
    cleaned_text = cleaned_text.strip()
    
    try:
        data = json.loads(cleaned_text)
        if isinstance(data, list):
            return data
        else:
            print("模型返回的不是列表格式")
            return None
    except json.JSONDecodeError:
        print(f"JSON解析失败，模型原始返回: {response_text[:100]}...")
        return None

# ================= 数据处理逻辑 =================

def process_single_line(line, output_file, write_lock):
    """处理单行数据"""
    try:
        data_line = json.loads(line)
    except:
        return False

    # 1. 提取原始文本
    raw_text = ""
    try:
        if 'target' in data_line and len(data_line['target']) > 0:
            raw_text = data_line['target'][0].get('question', '')
        
        if not raw_text:
            raw_text = data_line.get('body', '')
            
        if not raw_text:
            print(f"跳过：未找到文本内容")
            return False
    except Exception as e:
        print(f"数据解析异常: {e}")
        return False

    # 2. 准备图片
    image_urls = construct_image_urls(data_line)

    # 3. 获取服务URL
    try:
        service_url = get_thread_service_url()
    except:
        return False

    # 4. 调用模型
    model_response = call_qwen3_vl_model(image_urls, raw_text, service_url)
    
    if not model_response:
        return False

    # 5. 解析结果并构建输出
    parsed_qa = parse_model_response(model_response)
    
    if parsed_qa:
        # 构造新的结果对象
        result_record = {
            "img": data_line.get("img", []),
            "target": parsed_qa, # 这里替换为模型生成的图文对列表
            "prefix": data_line.get("prefix", ""),
            "origin": data_line.get("target", []) # 【新增】保存原始的图文交错数据
        }
        
        # 6. 写入文件
        with write_lock:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result_record, ensure_ascii=False) + '\n')
        return True
    else:
        return False

def process_jsonl_file(input_jsonl, output_jsonl):
    """主处理流程"""
    if not os.path.exists(input_jsonl):
        print(f"输入文件不存在: {input_jsonl}")
        return
    
    # 初始化输出文件
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        pass
    
    with open(input_jsonl, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    total_lines = len(lines)
    print(f"总任务数: {total_lines}")
    
    batch_size = 20000 # 批次大小
    num_batches = (total_lines + batch_size - 1) // batch_size
    write_lock = threading.Lock()
    
    total_success = 0
    thread_count = 256 # 并发数
    
    for batch_num in range(num_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, total_lines)
        batch_lines = lines[start:end]
        
        print(f"\n=== 处理批次 {batch_num+1}/{num_batches} (数量: {len(batch_lines)}) ===")
        
        thread_local.service_url = None
        
        pbar = tqdm(total=len(batch_lines))
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [
                executor.submit(process_single_line, line, output_jsonl, write_lock) 
                for line in batch_lines
            ]
            
            for future in as_completed(futures):
                try:
                    if future.result():
                        total_success += 1
                except Exception as e:
                    print(f"任务异常: {e}")
                finally:
                    pbar.update(1)
        
        pbar.close()
        print(f"当前累计成功: {total_success}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <input.jsonl> <output.jsonl>")
        sys.exit(1)
    
    process_jsonl_file(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    main()