import os
import json
import sys
import shutil
from paddleocr import PaddleOCRVL
from pdf2image import convert_from_path


def pdf_to_jsonl_paddle_vl(pdf_path, jsonl_filename, output_dir="output_results"):
    """
    使用 PaddleOCR-VL 将 PDF 解析为 JSONL 数据
    每一行代表一页的解析结果
    """
    
    # 1. 初始化模型
    print("正在加载 PaddleOCR-VL 模型...")
    pipeline = PaddleOCRVL()


    # 检查输出目录是否存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)


    # 定义最终的 JSONL 输出路径
    jsonl_path = os.path.join(output_dir, jsonl_filename)
    
    # 初始化清空 JSONL 文件
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        pass


    print(f"正在处理文件: {pdf_path}")
    print(f"结果将输出到: {jsonl_path}")


    try:
        # 2. 将 PDF 转换为图片列表
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"读取 PDF 失败，请确保已安装 Poppler 工具。错误信息: {e}")
        return


    # 3. 逐页进行预测
    for i, image in enumerate(images):
        print(f"正在解析第 {i+1}/{len(images)} 页...")
        
        # 定义基础名称，例如 temp_page_0
        base_name = f"temp_page_{i}"
        
        # 临时图片路径: output_results/temp_page_0.png
        temp_img_path = os.path.join(output_dir, f"{base_name}.png")
        image.save(temp_img_path)


        try:
            # 调用预测
            output = pipeline.predict(temp_img_path)


            # 4. 处理结果并写入 JSONL
            for res in output:
                save_path_input = os.path.join(output_dir, base_name)
                
                # 保存结果
                res.save_to_json(save_path=save_path_input)
                target_json_path = os.path.join(save_path_input, f"{base_name}_res.json")
                
                if os.path.exists(target_json_path):
                    # 读取生成的 JSON 文件
                    with open(target_json_path, 'r', encoding='utf-8') as f_in:
                        page_data = json.load(f_in)
                    
                    # 修正页码信息
                    page_data['page_index'] = i
                    page_data['page_count'] = len(images)
                    # 修正输入路径为 PDF 路径
                    page_data['input_path'] = pdf_path


                    # 追加写入 JSONL 文件
                    with open(jsonl_path, 'a', encoding='utf-8') as f_out:
                        f_out.write(json.dumps(page_data, ensure_ascii=False) + "\n")
                    
                    print(f"第 {i+1} 页结果已追加至 JSONL 文件。")
                    
                    # --- 清理工作 ---
                    # 1. 删除生成的 json 文件
                    os.remove(target_json_path)
                    # 2. 删除 PaddleOCR 创建的子文件夹 (output_results/temp_page_0/)
                    if os.path.exists(save_path_input):
                        shutil.rmtree(save_path_input)
                        
                else:
                    print(f"警告: 未找到预期的 JSON 文件: {target_json_path}")
                    # 调试：如果还是找不到，打印一下子文件夹里到底有什么
                    if os.path.exists(save_path_input):
                        print(f"子文件夹内容: {os.listdir(save_path_input)}")


        except Exception as e:
            print(f"第 {i+1} 页解析出错: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 清理临时图片文件
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)


    print(f"所有处理完成！完整结果保存在: {jsonl_path}")


if __name__ == "__main__":
    # --- 配置区域 ---
    # LOCAL_PDF_PATH = "/home/tione/notebook/parsing/data/STEM_pdf_0123/Full-1.pdf" 
    LOCAL_PDF_PATH = sys.argv[1]
    jsonl_filename = sys.argv[2]
    # 开始转换
    pdf_to_jsonl_paddle_vl(LOCAL_PDF_PATH,jsonl_filename)