import os
import logging
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
import time
import traceback
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

from text_processor import TextProcessor
from translators import create_translator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'doc', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 限制上传文件大小为50MB
app.config['JSON_AS_ASCII'] = False  # 允许JSON响应包含非ASCII字符
# app.json.ensure_ascii = False

# 创建必要的文件夹
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

async def process_translation(file_path: str, api_type: str, api_key: str, model: str,
                            source_lang: str, target_lang: str,
                            system_prompt: str, user_prompt: str,
                            temperature: float) -> dict:
    try:
        # 处理文本
        processor = TextProcessor(max_tokens=2000)
        translator = create_translator(api_type, api_key)
        
        # 提取文本
        logger.info("开始提取文本内容")
        text = processor.extract_from_file(file_path)
        
        if not text or len(text.strip()) == 0:
            logger.error("提取的文本内容为空")
            return {'error': '提取的文本内容为空，请检查文件是否有效'}
            
        logger.info(f"文本提取完成，长度：{len(text)} 字符")
        
        # 处理文本
        logger.info("开始处理文本")
        chunks = processor.process_text(text)
        
        logger.info(f"文本处理完成，共分为 {len(chunks)} 个文本块")
        
        # 记录每个文本块的大小
        for i, (prev_text, current_text) in enumerate(chunks):
            logger.info(f"块 {i+1}: {len(current_text)} 字符")
            
        # 翻译文本
        logger.info(f"开始翻译，共 {len(chunks)} 个块")
        translated_chunks = []
        
        for i, (prev_text, current_text) in enumerate(chunks):
            logger.info(f"正在翻译第 {i+1}/{len(chunks)} 块...")
            translated_chunk = translator.translate(
                current_text, 
                source_lang=source_lang, 
                target_lang=target_lang,
                model=model,
                system_prompt=system_prompt if system_prompt else None,
                user_prompt=user_prompt if user_prompt else None,
                temperature=temperature
            )
            
            if translated_chunk:
                translated_chunks.append(translated_chunk)
                logger.info(f"块 {i+1} 翻译完成")
            else:
                logger.warning(f"块 {i+1} 翻译失败，将重试...")
                # 重试一次
                await asyncio.sleep(2)
                translated_chunk = translator.translate(
                    current_text, 
                    source_lang=source_lang, 
                    target_lang=target_lang,
                    model=model,
                    system_prompt=system_prompt if system_prompt else None,
                    user_prompt=user_prompt if user_prompt else None,
                    temperature=temperature
                )
                
                if translated_chunk:
                    translated_chunks.append(translated_chunk)
                    logger.info(f"块 {i+1} 重试翻译成功")
                else:
                    logger.error(f"块 {i+1} 翻译失败")
                    translated_chunks.append(f"[翻译失败] {current_text[:100]}...")
            
            # 防止API速率限制
            if i < len(chunks) - 1:
                await asyncio.sleep(2)
        
        # 合并翻译结果
        translated_text = '\n\n'.join(translated_chunks)
        
        # 生成输出文件名
        timestamp = int(time.time())
        output_filename = f"translated_{timestamp}_{os.path.basename(file_path)}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        # 保存翻译结果
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        
        logger.info(f"翻译完成，结果已保存至 {output_path}")
        
        return {
            'success': True,
            'message': '翻译完成',
            'output_file': output_filename
        }
        
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return {'error': f'处理失败: {str(e)}'}

@app.route('/upload', methods=['POST'])
async def upload_file():
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            logger.warning("没有文件被上传")
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            logger.warning("没有选择文件")
            return jsonify({'error': '没有选择文件'}), 400
        
        # 检查文件类型
        if not allowed_file(file.filename):
            logger.warning(f"不支持的文件类型: {file.filename}")
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # 安全地保存文件
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        filename_with_timestamp = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename_with_timestamp)
        file.save(file_path)
        
        logger.info(f"文件已保存: {file_path}")
        
        # 获取API类型和密钥
        api_type = request.form.get('api_type', 'deepseek')
        api_key = request.form.get('api_key', '')
        if not api_key:
            logger.warning("API密钥不能为空")
            return jsonify({'error': 'API密钥不能为空'}), 400
            
        # 获取模型
        model = request.form.get('model', '')
        if not model:
            logger.warning("未选择模型")
            return jsonify({'error': '请选择要使用的模型'}), 400
        
        # 获取温度参数
        temperature = float(request.form.get('temperature', 1.0))
        
        # 获取翻译方向
        source_lang = request.form.get('source_lang', '英文')
        target_lang = request.form.get('target_lang', '中文')
        
        # 获取自定义提示词
        system_prompt = request.form.get('system_prompt', '')
        user_prompt = request.form.get('user_prompt', '')
        
        logger.info(f"开始处理文件: {filename}, API类型: {api_type}, 模型: {model}, 温度: {temperature}")
        logger.info(f"源语言: {source_lang}, 目标语言: {target_lang}")
        
        # 处理翻译
        result = await process_translation(
            file_path, api_type, api_key, model,
            source_lang, target_lang,
            system_prompt, user_prompt,
            temperature
        )
        
        if 'error' in result:
            return jsonify(result), 500
        return jsonify(result)
            
    except Exception as e:
        logger.error(f"上传文件时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'上传失败: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename),
                     as_attachment=True)

@app.route('/translate', methods=['POST'])
async def interactive_translate():
    try:
        # 获取请求数据
        data = request.get_json()
        
        # 验证必要的参数
        if not data:
            return jsonify({'error': '未提供数据'}), 400
            
        user_message = data.get('user_message', '')
        if not user_message:
            return jsonify({'error': '翻译内容不能为空'}), 400
            
        api_type = data.get('api_type', 'deepseek')
        api_key = data.get('api_key', '')
        if not api_key:
            return jsonify({'error': 'API密钥不能为空'}), 400
            
        model = data.get('model', '')
        if not model:
            return jsonify({'error': '请选择要使用的模型'}), 400
            
        # 获取其他参数
        temperature = float(data.get('temperature', 1.0))
        source_lang = data.get('source_lang', '英文')
        target_lang = data.get('target_lang', '中文')
        system_prompt = data.get('system_prompt', '')
        
        logger.info(f"交互翻译请求: API类型: {api_type}, 模型: {model}, 温度: {temperature}")
        logger.info(f"源语言: {source_lang}, 目标语言: {target_lang}")
        
        # 创建翻译器
        translator = create_translator(api_type, api_key)
        
        # 执行翻译
        translated_text = translator.translate(
            user_message, 
            source_lang=source_lang, 
            target_lang=target_lang,
            model=model,
            system_prompt=system_prompt if system_prompt else None,
            user_prompt=None,  # 在交互模式中，用户消息直接作为内容
            temperature=temperature
        )
        
        if translated_text:
            return jsonify({
                'success': True,
                'translation': translated_text
            })
        else:
            return jsonify({'error': '翻译失败'}), 500
            
    except Exception as e:
        logger.error(f"交互翻译时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'翻译失败: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("翻译应用程序启动")
    # 使用hypercorn作为ASGI服务器
    import hypercorn.asyncio
    import hypercorn.config
    
    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = True
    
    asyncio.run(hypercorn.asyncio.serve(app, config)) 