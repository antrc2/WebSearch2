from duckduckgo_search import DDGS

def duckduckgo_search(query, max_results=20):
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results,region="vi-VN")
        return results

# Example usage
if __name__ == "__main__":
    query = "Giới thiệu về 'AI thông minh nhất trái đất'"
    search_results = duckduckgo_search(query)

    for i, result in enumerate(search_results, 1):
        print(f"{i}. {result['title']}")
        print(f"   {result['href']}")
        print(f"   {result['body']}\n")

    print(search_results)
