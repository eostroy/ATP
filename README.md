# 文档翻译工具

这是一个基于DeepSeek API的文档翻译工具，可以处理Word和TXT文档，并将其翻译成目标语言。

## 功能

1. **文件上传**: 支持上传Word(.docx/.doc)和文本(.txt)文档
2. **文本处理**: 自动清理文本并进行格式化，按自然段切分
3. **智能翻译**: 使用DeepSeek API进行高质量翻译
4. **下载结果**: 以TXT格式保存和下载翻译结果

## 安装

1. 确保您已安装Python 3.6+
2. 安装依赖包:

```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行Flask应用:

```bash
python book_translation.py
```

2. 在浏览器中打开 http://127.0.0.1:5000
3. 输入您的DeepSeek API密钥（您需要在[DeepSeek官网](https://www.deepseek.com/)申请）
4. 选择要翻译的文档
5. 选择源语言和目标语言
6. 点击"开始翻译"
7. 翻译完成后，点击下载链接获取翻译结果

## 项目结构

- `book_translation.py`: 主应用程序和Web界面
- `text_processor.py`: 处理文本的模块
- `deepseek_translator.py`: 调用DeepSeek API进行翻译
- `templates/index.html`: Web界面的HTML模板
- `uploads/`: 上传文件的临时存储目录
- `outputs/`: 翻译结果的存储目录

## 注意事项

- 需要有可用的DeepSeek API密钥
- 大型文档可能需要更长的处理时间
- 翻译质量取决于API的能力

## 自定义

您可以通过修改以下文件来自定义程序：

- `text_processor.py`: 调整文本处理参数和方法
- `deepseek_translator.py`: 调整API调用参数
- `templates/index.html`: 自定义用户界面

## 技术栈

- Python 3
- Flask
- DeepSeek API
- HTML/CSS/JavaScript 