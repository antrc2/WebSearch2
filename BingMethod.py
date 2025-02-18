import requests
from bs4 import BeautifulSoup
import bs4
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import CharacterTextSplitter
import requests
import faiss
import numpy as np
from openai import OpenAI
client = OpenAI(base_url="http://localhost:11434/v1",api_key="khong-can-thiet")
def get_embedding(text, model="text-embedding"):
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding

def askModel(messages):
    response = client.chat.completions.create(
    model="sailor",
    messages=messages,
    max_tokens=1024,
    temperature=0.1,
    stream=True
)
    generated_text = ""
    print("BeeAI: ",end="")
    for res in response:
        # print(res)
        text = res.choices[0].delta.content
        if(text):
            print(text, end="",flush=True)
            generated_text+=text
    messages.append(
        {
            "role": "assistant",
            "content": generated_text
        }
    )

query = input("Bạn: ")
url = f"https://www.bing.com/search?q={query}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.62 Safari/537.36"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

links = []
unique_domains = set()
filtered_links = []

# Lặp qua tất cả các thẻ <a> có class là 'tilk' trong trang HTML
for tag in soup.find_all('a', class_='tilk'):
    href = tag.get('href')  # Lấy đường link trong thuộc tính href của thẻ <a>
    
    # Kiểm tra xem đường link có hợp lệ và bắt đầu bằng 'https://'
    if href and href.startswith("https://"):
        domain = href.split("/")[2]  # Trích xuất domain từ đường link (chẳng hạn: 'www.example.com')
        
        # Kiểm tra nếu domain chưa có trong danh sách đã duyệt
        if domain not in unique_domains:
            try:
                # Gửi yêu cầu GET tới đường link và kiểm tra trạng thái trả về
                response = requests.get(href, timeout=1) 
                status_code = response.status_code  # Lấy mã trạng thái HTTP
            except requests.exceptions.RequestException as e:
                # Nếu gặp lỗi trong quá trình yêu cầu, đặt status_code là None
                status_code = None
            
            # Nếu mã trạng thái là 200, tức là trang web có thể truy cập được
            if status_code == 200:
                unique_domains.add(domain)  # Thêm domain vào danh sách đã duyệt
                print(f"Đang tìm kiếm tại trang web: {href}")  # In ra đường link đang kiểm tra
                filtered_links.append((tag.get_text(strip=True), href))  # Thêm tiêu đề và đường link vào danh sách các link hợp lệ

            # Dừng lại khi đã tìm đủ 3 trang web có domain khác nhau
            if len(unique_domains) >= 3:
                break  # Thoát khỏi vòng lặp khi đủ số lượng trang web

# Biến context dùng để lưu trữ nội dung các trang web
context = ""
# Lặp qua danh sách các link đã lọc để lấy nội dung của từng trang
for i, (text, href) in enumerate(filtered_links, start=1):
    # Tạo đối tượng WebBaseLoader để tải nội dung của trang từ đường link
    loader = WebBaseLoader(
        web_paths=(href,),  # Đường link của trang web
        bs_kwargs=dict(
            parse_only=bs4.SoupStrainer()  # Chỉ phân tích cú pháp của HTML mà không tải toàn bộ trang
        ),
    )
    docs = loader.load()
    
    # 3️⃣ Chia nhỏ văn bản
    text_splitter = CharacterTextSplitter(
        chunk_size=2000, 
        chunk_overlap=200,
        separator="\n",
        length_function=len
    )
    texts = text_splitter.split_documents(docs)

    # 4️⃣ Tạo embedding và vector database
    embedding_vectors = [get_embedding(doc.page_content) for doc in texts]

    # Chuyển đổi embedding vectors thành numpy array
    embedding_vectors_np = np.array(embedding_vectors).astype(np.float32)

    # Tạo FAISS index
    dim = embedding_vectors_np.shape[1]  # Số chiều của embedding
    # print(embedding_vectors_np.shape[1])
    index = faiss.IndexFlatL2(dim)

    # Thêm các embedding vào FAISS index
    index.add(embedding_vectors_np)

    # Lưu index vào thư mục
    faiss.write_index(index, "faiss_index.index")


query_embedding = get_embedding(query)
query_embedding_np = np.array([query_embedding]).astype(np.float32)
# Truy vấn FAISS để lấy 3 kết quả gần nhất
k = 3
_, indices = index.search(query_embedding_np, k)

# Lấy các tài liệu tương ứng từ indices
context_docs = [texts[i] for i in indices[0]]
messages = [
        {
            "role": "system", 
            "content": f"""Bạn là một trợ lý AI được thiết kế để trả lời các câu hỏi của người dùng một cách ngắn gọn và chính xác. .
            """
        },
        {
            "role": "user", 
            "content": f"""Những câu hỏi mà tôi sắp hỏi, bạn chỉ được trả lời ở phần ngữ cảnh thôi nhé. Bạn chỉ có quyền truy cập vào ngữ cảnh đã được cung cấp. 
Nếu bạn không tìm thấy câu trả lời phù hợp trong ngữ cảnh, hãy thành thật thừa nhận rằng bạn không biết. 
Ví dụ: "Xin lỗi, tôi không có thông tin về điều đó." 
Hãy tránh đưa ra các câu trả lời không chính xác hoặc suy đoán .
Ngữ cảnh: {context}"""
        },
        {
            "role": "assistant",
            "content": "Từ giờ tôi sẽ chỉ trả lời ở trong phần ngữ cảnh mà bạn đã yêu cầu."
        },
        {
            "role": "user",
            "content": f"{query}"
        }
]
askModel(messages)
print()

while True:
    user_input = input("Bạn: ")
    if(user_input == "quit"):
        break
    messages.append(
    {
        "role": "user",
        "content": user_input
    }
)   
    askModel(messages)
    print()