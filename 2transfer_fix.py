import json
import hashlib
import os
import sys
from typing import List, Dict
from pdf2image import convert_from_path
from PIL import Image




def load_json_data(file_path: str) -> List[Dict]:
    """加载JSONL文件，每行一个JSON对象"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data




def is_visual_element(label: str) -> bool:
    """判断是否为图片/图表元素"""
    return label in ['image', 'chart', 'table']




def is_figure_title(label: str) -> bool:
    """判断是否为图表标题"""
    return label == 'figure_title'




def is_paragraph_title(label: str) -> bool:
    """判断是否为段落标题"""
    return label == 'paragraph_title'




def is_text(label: str) -> bool:
    """判断是否为文本"""
    return label == 'text'




def is_relevant_element(label: str) -> bool:
    """判断是否为相关元素（段落标题、文本、图表、图表标题）"""
    return (is_paragraph_title(label) or is_text(label) or 
            is_visual_element(label) or is_figure_title(label))




def generate_hash_filename(content: str) -> str:
    """生成32位MD5哈希值作为文件名"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()




def crop_image_from_pdf(pdf_path: str, page_index: int, bbox: List[int], 
                        output_dir: str, dpi: int = 300) -> str:
    """
    从PDF中截取指定区域的图片
    
    Args:
        pdf_path: PDF文件路径
        page_index: 页码索引（从0开始）
        bbox: 边界框 [x1, y1, x2, y2]
        output_dir: 输出目录
        dpi: 转换DPI
    
    Returns:
        相对路径（包含二级目录和文件名）
    """
    # 生成唯一的哈希文件名
    hash_content = f"{pdf_path}_{page_index}_{bbox}"
    hash_name = generate_hash_filename(hash_content)
    
    # 使用前3位作为二级目录
    sub_dir = hash_name[:3]
    full_sub_dir = os.path.join(output_dir, sub_dir)
    
    # 创建二级目录
    os.makedirs(full_sub_dir, exist_ok=True)
    
    # 完整文件路径
    filename = f"{hash_name}.jpg"
    full_path = os.path.join(full_sub_dir, filename)
    
    # 如果文件已存在，直接返回相对路径
    relative_path = os.path.join(sub_dir, filename)
    if os.path.exists(full_path):
        return relative_path
    
    # 转换PDF页面为图片
    images = convert_from_path(pdf_path, dpi=dpi, first_page=page_index+1, last_page=page_index+1)
    
    if not images:
        raise ValueError(f"无法从PDF中提取第 {page_index+1} 页")
    
    page_image = images[0]
    
    # 截取指定区域
    # bbox格式: [x1, y1, x2, y2]
    cropped_image = page_image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
    
    # 保存图片
    cropped_image.save(full_path, 'JPEG', quality=95)
    
    return relative_path




def extract_all_blocks(pages_data: List[Dict]) -> List[Dict]:
    """
    从所有页面提取相关的块，并添加页面信息
    返回格式: [{'block': block_info, 'page_index': int, 'block_id': int, 'pdf_path': str}, ...]
    """
    all_blocks = []
    
    for page_data in pages_data:
        page_index = page_data.get('page_index', 0)
        pdf_path = page_data.get('input_path', '')
        parsing_res = page_data.get('parsing_res_list', [])
        
        for block in parsing_res:
            label = block.get('block_label', '')
            if is_relevant_element(label):
                all_blocks.append({
                    'block': block,
                    'page_index': page_index,
                    'pdf_path': pdf_path,
                    'block_id': block.get('block_id', 0)  # 使用block_id
                })
    
    # 按照页面索引和block_id排序
    all_blocks.sort(key=lambda x: (x['page_index'], x['block_id']))
    
    return all_blocks




def has_figure_with_title(blocks: List[Dict], start_idx: int, end_idx: int) -> bool:
    """
    判断指定范围内是否包含带标题的图表
    逻辑：检查是否存在图表元素，且其相邻元素中包含figure_title
    """
    segment = blocks[start_idx:end_idx]
    
    for i, item in enumerate(segment):
        label = item['block'].get('block_label', '')
        
        if is_visual_element(label):
            # 检查前一个元素
            if i > 0 and is_figure_title(segment[i-1]['block'].get('block_label', '')):
                return True
            
            # 检查后一个元素
            if i < len(segment) - 1 and is_figure_title(segment[i+1]['block'].get('block_label', '')):
                return True
    
    return False




def extract_paragraphs_with_figures(pages_data: List[Dict], image_output_dir: str) -> List[Dict]:
    """
    提取包含带标题图表的段落，并转换为指定格式
    
    Args:
        pages_data: 页面数据列表
        image_output_dir: 图片输出目录
    
    Returns:
        转换后的数据列表
    """
    all_blocks = extract_all_blocks(pages_data)
    
    if not all_blocks:
        return []
    
    # 找到所有段落标题的索引
    paragraph_title_indices = [
        i for i, item in enumerate(all_blocks) 
        if is_paragraph_title(item['block'].get('block_label', ''))
    ]
    
    if not paragraph_title_indices:
        return []
    
    # 提取符合条件的段落
    result_data = []
    
    for i, start_idx in enumerate(paragraph_title_indices):
        # 确定段落结束位置
        end_idx = paragraph_title_indices[i + 1] if i < len(paragraph_title_indices) - 1 else len(all_blocks)
        
        # 检查该段落是否包含带标题的图表
        if has_figure_with_title(all_blocks, start_idx, end_idx):
            img_list = []
            question_parts = []
            
            for item in all_blocks[start_idx:end_idx]:
                block = item['block']
                label = block.get('block_label', '')
                content = block.get('block_content', '').strip()
                
                if is_visual_element(label):
                    # 检查图片尺寸
                    bbox = block.get('block_bbox', [])
                    if len(bbox) >= 4:
                        width = bbox[2] - bbox[0]
                        height = bbox[3] - bbox[1]
                        
                        # 过滤小于120*120的图片
                        if width < 120 or height < 120:
                            print(f"Skipping small image: {width}x{height}")
                            continue
                    
                    # 截取图片
                    pdf_path = item['pdf_path']
                    page_index = item['page_index']
                    
                    try:
                        # 截取并保存图片
                        relative_path = crop_image_from_pdf(
                            pdf_path, page_index, bbox, image_output_dir
                        )
                        
                        # 添加到图片列表
                        img_list.append(relative_path)
                        
                        # 添加图片占位符（使用当前img_list的长度-1作为索引）
                        img_index = len(img_list) - 1
                        placeholder = f"<ut_im##age_here_index>{img_index}</ut_im##age_here_index>"
                        question_parts.append(placeholder)
                        
                    except Exception as e:
                        print(f"截取图片失败: {e}")
                        continue
                        
                elif is_text(label) or is_paragraph_title(label) or is_figure_title(label):
                    # 添加文本内容
                    if content:
                        question_parts.append(content)
            
            # 只有当存在图片时才添加到结果中
            if img_list:
                # 用换行符连接所有部分
                question = '\n'.join(question_parts)
                
                result_data.append({
                    'img': img_list,
                    'target': [{
                        'question': question,
                        'answer': ''
                    }],
                    'prefix': '/cfs-40796a3b3/private/holdenlin/parsing/code/repo'
                })
    
    return result_data




def process_pdf_data(input_file: str, output_file: str, image_output_dir: str = "repo"):
    """
    处理PDF数据并保存结果
    
    Args:
        input_file: 输入的JSONL文件路径
        output_file: 输出的JSONL文件路径
        image_output_dir: 图片输出目录
    """
    print(f"Loading data from {input_file}...")
    pages_data = load_json_data(input_file)
    print(f"Loaded {len(pages_data)} pages")
    
    # 创建图片输出目录
    os.makedirs(image_output_dir, exist_ok=True)
    
    print("Extracting paragraphs with figures...")
    result_data = extract_paragraphs_with_figures(pages_data, image_output_dir)
    print(f"Found {len(result_data)} valid paragraphs")
    
    print(f"Saving results to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in result_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    print("Done!")
    return result_data




if __name__ == "__main__":
    # input_file = "/home/tione/notebook/parsing/code/output_results/result.jsonl"
    # output_file = "output_paragraphs_3.jsonl"
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    image_output_dir = "repo"  # 图片存储目录
    
    process_pdf_data(input_file, output_file, image_output_dir)