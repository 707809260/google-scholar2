import pandas as pd
import time
import requests
import os
import random
from scholarly import scholarly, ProxyGenerator

# --- 1. 配置 DeepSeek API --- 
DEEPSEEK_API_KEY = "你的deepseek API-key"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
OUTPUT_FILE = "Silk_Road_Literature_Categorized.csv"

# --- 2. 检查并加载已有的条目 (去重核心) --- 可以反复执行这个代码，新结果增加到旧表格里
def load_existing_titles(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            # 返回标题集合，用于快速查找
            return set(df['Title'].dropna().tolist())
        except Exception as e:
            print(f"读取旧文件失败: {e}")
            return set()
    return set()

existing_titles = load_existing_titles(OUTPUT_FILE)
print(f"已加载 {len(existing_titles)} 条现有文献，抓取时将自动跳过。")

# --- 3. 精细化分类逻辑 ---让deepseek执行识别内容打标签的工作
SYSTEM_PROMPT = """
你是一名学术文献分析专家。请根据以下五个维度，对输入的学术条目进行分类（只需输出类别代码）：
- 看看想给搜到的文献打上什么标签
- 
- 
- 
- 
- 
"""

def get_deepseek_category(title, snippet):
    content = f"标题: {title}\n摘要: {snippet}"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        "temperature": 0.2
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        return res.json()['choices'][0]['message']['content'].strip()
    except:
        return "ERROR"

# --- 4. 执行抓取与实时写入 ---
def incremental_collect(queries, results_per_query=30):
    for query in queries:
        print(f"\n>>> 正在检索关键词: {query}")
        search_query = scholarly.search_pubs(query)
        
        count = 0
        while count < results_per_query:
            try:
                pub = next(search_query)
                bib = pub.get('bib', {})
                title = bib.get('title', 'N/A')
                
                # 去重判断
                if title in existing_titles:
                    # print(f"  [-] 跳过已存在条目: {title[:30]}...")
                    continue
                
                snippet = bib.get('abstract', '')
                category = get_deepseek_category(title, snippet)
                
                if category != "IGNORE":
                    item = {
                        "Category": category,
                        "Title": title,
                        "Author": bib.get('author', 'N/A'),
                        "Year": bib.get('pub_year', 'N/A'),
                        "Source": bib.get('venue', 'N/A'),
                        "Citations": pub.get('num_citations', 0),
                        "Link": pub.get('pub_url', 'N/A'),
                        "Snippet": snippet
                    }
                    
                    # 实时保存：以追加模式写入，不包含 Header
                    pd.DataFrame([item]).to_csv(OUTPUT_FILE, mode='a', 
                                                index=False, 
                                                header=not os.path.exists(OUTPUT_FILE), 
                                                encoding='utf-8-sig')
                    
                    existing_titles.add(title) # 同步更新本地黑名单
                    print(f"  [√] 新增收录: {title[:40]}... ({category})")
                
                count += 1
                time.sleep(1.5) # 稍微延长等待，降低被封风险
                
            except StopIteration:
                break
            except Exception as e:
                print(f"  [!] 访问受限或错误: {e}")
                time.sleep(10) # 遇错多等一会
                break

# --- 5. 启动 ---在list可以按格式自行添加
search_list = [
    '"Silk Road" (geographic knowledge OR "land measurement" OR survey) service',
    '“丝绸之路” (地理知识 OR 测绘 OR 步测 OR 地方志) 服务',
]

incremental_collect(search_list)
print(f"\n抓取任务结束。当前库中共有 {len(existing_titles)} 条文献。")
